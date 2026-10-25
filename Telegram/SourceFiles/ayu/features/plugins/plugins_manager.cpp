// This is the source code of AyuGram for Desktop.
//
// We do not and cannot prevent the use of our code,
// but be respectful and credit the original author.
//
// Copyright @Radolyn, 2026
#include "ayu/features/plugins/plugins_manager.h"

#include "api/api_common.h"
#include "apiwrap.h"
#include "boxes/abstract_box.h"
#include "core/application.h"
#include "core/version.h"
#include "data/data_peer.h"
#include "data/data_session.h"
#include "history/history.h"
#include "history/history_item.h"
#include "main/main_account.h"
#include "main/main_domain.h"
#include "main/main_session.h"
#include "mtproto/details/mtproto_serialized_request.h"
#include "mtproto/mtproto_response.h"
#include "styles/style_layers.h"
#include "styles/style_menu_icons.h"
#include "ui/layers/generic_box.h"
#include "ui/toast/toast.h"
#include "ui/widgets/fields/input_field.h"
#include "ui/widgets/labels.h"
#include "ui/widgets/popup_menu.h"

#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QThread>
#include <QtGui/QClipboard>
#include <QtGui/QGuiApplication>

#ifdef Q_OS_WIN
#include <windows.h>

// WHY: Qt defines `slots` as a macro and Python headers use it as a field
// name; _DEBUG would make pyconfig.h demand the debug python311_d.lib.
#pragma push_macro("slots")
#undef slots
#ifdef _DEBUG
#undef _DEBUG
#include <Python.h>
#define _DEBUG
#else // _DEBUG
#include <Python.h>
#endif // _DEBUG
#pragma pop_macro("slots")
#endif // Q_OS_WIN

namespace AyuPlugins {
namespace {

#ifdef Q_OS_WIN
PyObject *Loader = nullptr;
#endif // Q_OS_WIN

rpl::event_stream<> Changes;
bool Available = false;
bool MessageHooks = false;
bool UpdateHooks = false;
base::flat_set<mtpTypeId> RequestHooks;
base::flat_set<mtpRequestId> HookedRequests;
base::flat_map<int64, QPointer<Ui::GenericBox>> Dialogs;

[[nodiscard]] QString PythonPath() {
	return cExeDir() + u"python/"_q;
}

[[nodiscard]] QString DataPath() {
	return cWorkingDir() + u"tdata/ayu/plugins_data/"_q;
}

[[nodiscard]] int64 ToInt64(const QJsonValue &value) {
	return int64(value.toDouble());
}

[[nodiscard]] int64 DialogId(PeerId id) {
	if (peerIsUser(id)) {
		return int64(peerToUser(id).bare);
	} else if (peerIsChat(id)) {
		return -int64(peerToChat(id).bare);
	}
	return -int64(peerToChannel(id).bare);
}

[[nodiscard]] PeerId PeerFromDialogId(
		not_null<Main::Session*> session,
		int64 id) {
	if (id > 0) {
		return peerFromUser(UserId(id));
	}
	const auto channel = peerFromChannel(ChannelId(-id));
	return session->data().peerLoaded(channel)
		? channel
		: peerFromChat(ChatId(-id));
}

[[nodiscard]] int AccountIndex(not_null<Main::Session*> session) {
	for (const auto &[index, account] : Core::App().domain().accounts()) {
		if (account.get() == &session->account()) {
			return index;
		}
	}
	return 0;
}

[[nodiscard]] std::optional<int> AccountIndex(
		not_null<MTP::Instance*> instance) {
	if (QThread::currentThread() != qApp->thread()) {
		return std::nullopt;
	}
	for (const auto &[index, account] : Core::App().domain().accounts()) {
		if (account->sessionExists() && &account->mtp() == instance) {
			return index;
		}
	}
	return std::nullopt;
}

[[nodiscard]] QString EncodeBuffer(const mtpPrime *data, int size) {
	return QString::fromLatin1(QByteArray(
		reinterpret_cast<const char*>(data),
		size * sizeof(mtpPrime)).toBase64());
}

[[nodiscard]] mtpBuffer DecodeBuffer(const QJsonValue &value) {
	const auto bytes = QByteArray::fromBase64(value.toString().toLatin1());
	auto result = mtpBuffer(bytes.size() / sizeof(mtpPrime));
	memcpy(result.data(), bytes.constData(), result.size() * sizeof(mtpPrime));
	return result;
}

[[nodiscard]] Main::Session *SessionByIndex(const QJsonValue &index) {
	auto &domain = Core::App().domain();
	if (!index.isNull() && !index.isUndefined()) {
		for (const auto &[i, account] : domain.accounts()) {
			if (i == index.toInt() && account->sessionExists()) {
				return &account->session();
			}
		}
	}
	return domain.active().sessionExists()
		? &domain.active().session()
		: nullptr;
}

[[nodiscard]] QJsonObject MessageJson(not_null<HistoryItem*> item) {
	return {
		{ u"id"_q, qint64(item->id.bare) },
		{ u"text"_q, item->originalText().text },
		{ u"date"_q, qint64(item->date()) },
		{ u"out"_q, item->out() },
		{ u"dialog_id"_q, qint64(DialogId(item->history()->peer->id)) },
		{ u"from_id"_q, qint64(DialogId(item->from()->id)) },
	};
}

[[nodiscard]] HistoryItem *FindMessage(const QJsonObject &args) {
	const auto session = SessionByIndex(args[u"account"_q]);
	if (!session) {
		return nullptr;
	}
	const auto peer = PeerFromDialogId(
		session,
		ToInt64(args[u"peer"_q]));
	return session->data().message(peer, MsgId(ToInt64(args[u"id"_q])));
}

void ApplyLocalChanges(
		not_null<HistoryItem*> item,
		const QJsonObject &changes) {
	if (changes.contains(u"text"_q)) {
		item->setText({ changes[u"text"_q].toString() });
		item->history()->owner().requestItemTextRefresh(item);
	}
	if (changes.contains(u"date"_q)) {
		item->setLocalDate(TimeId(ToInt64(changes[u"date"_q])));
	}
}

#ifdef Q_OS_WIN

QJsonObject CallRaw(const QString &method, const QJsonObject &args);

QJsonValue Call(const QString &method, const QJsonObject &args = {}) {
	const auto result = CallRaw(method, args);
	return result[u"ok"_q].toBool() ? result[u"result"_q] : QJsonValue();
}

void PluginDialogBox(
		not_null<Ui::GenericBox*> box,
		int64 token,
		const QJsonObject &args) {
	box->setTitle(rpl::single(args[u"title"_q].toString()));
	const auto message = args[u"message"_q].toString();
	if (!message.isEmpty()) {
		box->addRow(object_ptr<Ui::FlatLabel>(box, message, st::boxLabel));
	}
	auto fields = std::vector<not_null<Ui::InputField*>>();
	for (const auto &value : args[u"fields"_q].toArray()) {
		const auto field = value.toObject();
		fields.push_back(box->addRow(object_ptr<Ui::InputField>(
			box,
			st::defaultInputField,
			(field[u"multiline"_q].toBool()
				? Ui::InputField::Mode::MultiLine
				: Ui::InputField::Mode::SingleLine),
			rpl::single(field[u"hint"_q].toString()),
			field[u"text"_q].toString())));
	}
	if (!fields.empty()) {
		box->setFocusCallback([=] {
			fields.front()->setFocusFast();
		});
	}
	const auto weak = QPointer<Ui::GenericBox>(box.get());
	const auto buttons = args[u"buttons"_q].toArray();
	// Python sends neutral, negative, positive; the box adds right to left.
	for (auto i = buttons.size(); i != 0;) {
		const auto button = buttons[--i].toObject();
		const auto which = button[u"which"_q].toInt();
		const auto click = [=] {
			auto values = QJsonArray();
			for (const auto field : fields) {
				values.push_back(field->getLastText());
			}
			const auto result = Call(u"dialog_button"_q, {
				{ u"token"_q, token },
				{ u"which"_q, which },
				{ u"values"_q, values },
			}).toObject();
			if (weak && result[u"dismiss"_q].toBool()) {
				weak->closeBox();
			}
		};
		const auto text = rpl::single(button[u"text"_q].toString());
		if (which == -3) {
			box->addLeftButton(text, click);
		} else {
			box->addButton(text, click);
		}
	}
	box->boxClosing() | rpl::on_next([=] {
		Dialogs.remove(token);
		Call(u"dialog_closed"_q, { { u"token"_q, token } });
	}, box->lifetime());
}

QJsonValue HandleNative(const QString &method, const QJsonObject &args) {
	if (method == u"toast"_q) {
		Ui::Toast::Show(args[u"text"_q].toString());
	} else if (method == u"clipboard"_q) {
		QGuiApplication::clipboard()->setText(args[u"text"_q].toString());
	} else if (method == u"call_later"_q) {
		const auto token = ToInt64(args[u"token"_q]);
		crl::on_main([=] {
			Call(u"callback"_q, { { u"token"_q, token } });
		});
	} else if (method == u"send_text"_q) {
		const auto session = SessionByIndex(args[u"account"_q]);
		if (!session) {
			return {};
		}
		const auto peer = PeerFromDialogId(
			session,
			ToInt64(args[u"peer"_q]));
		auto action = Api::SendAction(session->data().history(peer));
		if (const auto reply = ToInt64(args[u"reply_to"_q])) {
			action.replyTo.messageId = FullMsgId(peer, MsgId(reply));
		}
		auto message = Api::MessageToSend(action);
		message.textWithTags = { args[u"text"_q].toString() };
		session->api().sendMessage(std::move(message));
	} else if (method == u"edit_local"_q) {
		if (const auto item = FindMessage(args)) {
			ApplyLocalChanges(item, args);
		}
	} else if (method == u"dialog_show"_q) {
		const auto token = ToInt64(args[u"token"_q]);
		Dialogs[token] = Ui::show(Box(PluginDialogBox, token, args)).get();
	} else if (method == u"dialog_dismiss"_q) {
		const auto i = Dialogs.find(ToInt64(args[u"token"_q]));
		if (i != end(Dialogs)) {
			const auto box = i->second;
			Dialogs.erase(i);
			if (box) {
				box->closeBox();
			}
		}
	} else if (method == u"get_message"_q) {
		if (const auto item = FindMessage(args)) {
			return MessageJson(item);
		}
	}
	return {};
}

PyObject *NativeRequest(PyObject *self, PyObject *args) {
	const char *method = nullptr;
	const char *json = nullptr;
	if (!PyArg_ParseTuple(args, "ss", &method, &json)) {
		return nullptr;
	}
	const auto name = QString::fromUtf8(method);
	const auto object = QJsonDocument::fromJson(json).object();
	if (QThread::currentThread() != qApp->thread()) {
		crl::on_main([=] { HandleNative(name, object); });
		return Py_BuildValue(""); // Py_RETURN_NONE imports data, breaks /DELAYLOAD
	}
	const auto result = QJsonDocument(QJsonObject{
		{ u"result"_q, HandleNative(name, object) },
	}).toJson(QJsonDocument::Compact);
	return PyUnicode_FromStringAndSize(result.constData(), result.size());
}

PyMethodDef NativeMethods[] = {
	{ "request", NativeRequest, METH_VARARGS, nullptr },
	{ nullptr, nullptr, 0, nullptr },
};

PyModuleDef NativeModule = {
	PyModuleDef_HEAD_INIT,
	"_ayugram",
	nullptr,
	-1,
	NativeMethods,
};

PyObject *InitNativeModule() {
	return PyModule_Create(&NativeModule);
}

QJsonObject CallRaw(const QString &method, const QJsonObject &args) {
	if (!Loader) {
		return {};
	}
	const auto json = QJsonDocument(args).toJson(QJsonDocument::Compact);
	const auto gil = PyGILState_Ensure();
	auto result = QJsonObject();
	if (const auto value = PyObject_CallMethod(
			Loader,
			"handle",
			"ss",
			method.toUtf8().constData(),
			json.constData())) {
		auto size = Py_ssize_t();
		if (const auto data = PyUnicode_AsUTF8AndSize(value, &size)) {
			result = QJsonDocument::fromJson(
				QByteArray(data, size)).object();
		}
		Py_DECREF(value);
	}
	if (PyErr_Occurred()) {
		PyErr_Print();
	}
	PyGILState_Release(gil);
	if (result[u"ok"_q].toBool()) {
		MessageHooks = result[u"message_hooks"_q].toBool();
		UpdateHooks = result[u"update_hooks"_q].toBool();
		RequestHooks.clear();
		for (const auto &id : result[u"request_hooks"_q].toArray()) {
			RequestHooks.emplace(mtpTypeId(uint32(id.toDouble())));
		}
	} else {
		LOG(("Plugins: %1 failed: %2"
			).arg(method
			).arg(result[u"error"_q].toString()));
	}
	return result;
}

[[nodiscard]] bool InitPython() {
	const auto home = QDir::toNativeSeparators(PythonPath()).toStdWString();
	const auto dll = home + L"python311.dll";
	if (!LoadLibraryExW(
			dll.c_str(),
			nullptr,
			LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR
				| LOAD_LIBRARY_SEARCH_DEFAULT_DIRS)) {
		LOG(("Plugins: python runtime not found in %1"
			).arg(PythonPath()));
		return false;
	}
	PyImport_AppendInittab("_ayugram", &InitNativeModule);

	auto config = PyConfig();
	PyConfig_InitIsolatedConfig(&config);
	config.install_signal_handlers = 0;
	config.write_bytecode = 0;
	config.site_import = 0;
	PyConfig_SetString(&config, &config.home, home.c_str());
	config.module_search_paths_set = 1;
	for (const auto &path : { L"Lib", L"DLLs", L"sdk" }) {
		PyWideStringList_Append(
			&config.module_search_paths,
			(home + path).c_str());
	}
	const auto status = Py_InitializeFromConfig(&config);
	PyConfig_Clear(&config);
	if (PyStatus_Exception(status)) {
		LOG(("Plugins: python init failed: %1"
			).arg(QString::fromUtf8(status.err_msg ? status.err_msg : "")));
		return false;
	}
	Loader = PyImport_ImportModule("ayu_plugins");
	if (!Loader) {
		PyErr_Print();
		LOG(("Plugins: could not import ayu_plugins"));
	}
	// Hooks re-acquire the GIL, plugin threads need it released meanwhile.
	PyEval_SaveThread();
	return Loader != nullptr;
}

#else // Q_OS_WIN

QJsonObject CallRaw(const QString &method, const QJsonObject &args) {
	return {};
}

QJsonValue Call(const QString &method, const QJsonObject &args = {}) {
	return {};
}

[[nodiscard]] bool InitPython() {
	return false;
}

#endif // Q_OS_WIN

} // namespace

void init() {
	if (!InitPython()) {
		return;
	}
	Available = true;
	Call(u"init"_q, {
		{ u"plugins_dir"_q, QDir::toNativeSeparators(pluginsPath()) },
		{ u"data_dir"_q, QDir::toNativeSeparators(DataPath()) },
		{ u"app_version"_q, QString::fromLatin1(AppVersionStr) },
	});
}

bool available() {
	return Available;
}

QString pluginsPath() {
	return cWorkingDir() + u"tdata/ayu/plugins/"_q;
}

std::vector<PluginInfo> list() {
	auto result = std::vector<PluginInfo>();
	for (const auto &value : Call(u"list"_q).toArray()) {
		const auto plugin = value.toObject();
		result.push_back({
			.id = plugin[u"id"_q].toString(),
			.name = plugin[u"name"_q].toString(),
			.description = plugin[u"description"_q].toString(),
			.author = plugin[u"author"_q].toString(),
			.version = plugin[u"version"_q].toString(),
			.error = plugin[u"error"_q].toString(),
			.enabled = plugin[u"enabled"_q].toBool(),
			.hasSettings = plugin[u"has_settings"_q].toBool(),
		});
	}
	return result;
}

rpl::producer<> changes() {
	return Changes.events();
}

void setEnabled(const QString &id, bool enabled) {
	Call(u"set_enabled"_q, {
		{ u"id"_q, id },
		{ u"enabled"_q, enabled },
	});
	Changes.fire({});
}

QString install(const QString &path) {
	if (!Available) {
		return u"Python runtime is not available."_q;
	}
	const auto result = CallRaw(u"install"_q, {
		{ u"path"_q, QDir::toNativeSeparators(path) },
	});
	Changes.fire({});
	return result[u"ok"_q].toBool()
		? result[u"result"_q][u"error"_q].toString()
		: result[u"error"_q].toString();
}

void uninstall(const QString &id) {
	Call(u"uninstall"_q, { { u"id"_q, id } });
	Changes.fire({});
}

QJsonArray settings(const QString &id) {
	return Call(u"settings"_q, { { u"id"_q, id } }).toArray();
}

void setSetting(const QString &id, const QString &key, const QJsonValue &value) {
	Call(u"settings_set"_q, {
		{ u"id"_q, id },
		{ u"key"_q, key },
		{ u"value"_q, value },
	});
}

void clickSetting(const QString &id, int index) {
	Call(u"settings_click"_q, {
		{ u"id"_q, id },
		{ u"index"_q, index },
	});
}

bool onSendMessage(
		not_null<Main::Session*> session,
		Api::MessageToSend &message) {
	if (!Available) {
		return true;
	}
	const auto &action = message.action;
	const auto result = Call(u"send_message"_q, {
		{ u"account"_q, AccountIndex(session) },
		{ u"params"_q, QJsonObject{
			{ u"peer"_q, qint64(DialogId(action.history->peer->id)) },
			{ u"message"_q, message.textWithTags.text },
			{ u"reply_to_msg_id"_q, qint64(action.replyTo.messageId.msg.bare) },
		} },
	}).toObject();
	const auto strategy = result[u"strategy"_q].toString();
	if (strategy == u"cancel"_q) {
		return false;
	} else if (strategy == u"modify"_q) {
		const auto text = result[u"message"_q].toString();
		if (text != message.textWithTags.text) {
			// shortcut: formatting is dropped when a plugin rewrites the text, map tags if plugins need it.
			message.textWithTags = { text };
		}
	}
	return true;
}

void onMessageCreated(not_null<HistoryItem*> item) {
	if (!Available || !MessageHooks || item->isService()) {
		return;
	}
	const auto changes = Call(u"message_bind"_q, {
		{ u"account"_q, AccountIndex(&item->history()->session()) },
		{ u"message"_q, MessageJson(item) },
	}).toObject();
	if (!changes.isEmpty()) {
		ApplyLocalChanges(item, changes);
	}
}

void fillMessageMenu(
		not_null<Ui::PopupMenu*> menu,
		not_null<HistoryItem*> item) {
	if (!Available) {
		return;
	}
	const auto items = Call(u"menu_items"_q, {
		{ u"menu_type"_q, u"MESSAGE_CONTEXT_MENU"_q },
	}).toArray();
	if (items.isEmpty()) {
		return;
	}
	const auto context = QJsonObject{
		{ u"account"_q, AccountIndex(&item->history()->session()) },
		{ u"dialog_id"_q, qint64(DialogId(item->history()->peer->id)) },
		{ u"message"_q, MessageJson(item) },
	};
	for (const auto &value : items) {
		const auto entry = value.toObject();
		const auto plugin = entry[u"plugin"_q].toString();
		const auto id = entry[u"item"_q].toString();
		menu->addAction(entry[u"text"_q].toString(), [=] {
			Call(u"menu_click"_q, {
				{ u"plugin"_q, plugin },
				{ u"item"_q, id },
				{ u"context"_q, context },
			});
		}, &st::menuIconCustomize);
	}
}

bool onRequest(
		not_null<MTP::Instance*> instance,
		mtpRequestId requestId,
		MTP::details::SerializedRequest &request) {
	using MTP::details::SerializedRequest;
	constexpr auto kBody = SerializedRequest::kMessageBodyPosition;
	if (RequestHooks.empty()
		|| request->size() <= kBody
		|| !RequestHooks.contains(mtpTypeId((*request)[kBody]))) {
		return true;
	}
	const auto account = AccountIndex(instance);
	if (!account) {
		return true;
	}
	const auto result = Call(u"request"_q, {
		{ u"account"_q, *account },
		{ u"request_id"_q, requestId },
		{ u"data"_q, EncodeBuffer(
			request->constData() + kBody,
			request->size() - kBody) },
	}).toObject();
	if (result[u"cancel"_q].toBool()) {
		return false;
	}
	HookedRequests.emplace(requestId);
	const auto body = DecodeBuffer(result[u"data"_q]);
	if (!body.isEmpty()) {
		auto replaced = SerializedRequest::Prepare(body.size());
		replaced->append(body);
		replaced->forceSendInContainer = request->forceSendInContainer;
		request = std::move(replaced);
	}
	return true;
}

std::optional<mtpBuffer> onResponse(
		not_null<MTP::Instance*> instance,
		const MTP::Response &response) {
	if (!HookedRequests.remove(response.requestId)) {
		return std::nullopt;
	}
	const auto account = AccountIndex(instance);
	if (!account || response.reply.isEmpty()) {
		return std::nullopt;
	}
	const auto result = Call(u"response"_q, {
		{ u"account"_q, *account },
		{ u"request_id"_q, response.requestId },
		{ u"data"_q, EncodeBuffer(
			response.reply.constData(),
			response.reply.size()) },
	}).toObject();
	auto reply = DecodeBuffer(result[u"data"_q]);
	return reply.isEmpty() ? std::nullopt : std::make_optional(reply);
}

std::optional<mtpBuffer> onUpdates(
		not_null<MTP::Instance*> instance,
		const MTP::Response &message) {
	if (!UpdateHooks || message.reply.isEmpty()) {
		return std::nullopt;
	}
	const auto account = AccountIndex(instance);
	if (!account) {
		return std::nullopt;
	}
	const auto result = Call(u"updates"_q, {
		{ u"account"_q, *account },
		{ u"data"_q, EncodeBuffer(
			message.reply.constData(),
			message.reply.size()) },
	}).toObject();
	if (result[u"drop"_q].toBool()) {
		return mtpBuffer();
	}
	auto reply = DecodeBuffer(result[u"data"_q]);
	return reply.isEmpty() ? std::nullopt : std::make_optional(reply);
}

} // namespace AyuPlugins
