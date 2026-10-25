// This is the source code of AyuGram for Desktop.
//
// We do not and cannot prevent the use of our code,
// but be respectful and credit the original author.
//
// Copyright @Radolyn, 2026
#include "ayu/ui/settings/settings_plugins.h"

#include "lang_auto.h"
#include "ayu/features/plugins/plugins_manager.h"
#include "core/file_utilities.h"
#include "settings/settings_common.h"
#include "styles/style_boxes.h"
#include "styles/style_layers.h"
#include "styles/style_menu_icons.h"
#include "styles/style_settings.h"
#include "ui/vertical_list.h"
#include "ui/boxes/confirm_box.h"
#include "ui/boxes/single_choice_box.h"
#include "ui/layers/generic_box.h"
#include "ui/widgets/buttons.h"
#include "ui/widgets/fields/input_field.h"
#include "ui/widgets/labels.h"
#include "ui/wrap/vertical_layout.h"
#include "window/window_session_controller.h"

#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtGui/QClipboard>
#include <QtGui/QDesktopServices>
#include <QtGui/QGuiApplication>

namespace Settings {
namespace {

constexpr auto kLogTailBytes = 32 * 1024;

[[nodiscard]] QString ReadLogTail() {
	auto file = QFile(AyuPlugins::logPath());
	if (!file.open(QIODevice::ReadOnly)) {
		return QString();
	}
	if (file.size() > kLogTailBytes) {
		file.seek(file.size() - kLogTailBytes);
		file.readLine();
	}
	return QString::fromUtf8(file.readAll()).trimmed();
}

void PluginsLogBox(not_null<Ui::GenericBox*> box) {
	box->setTitle(tr::ayu_PluginsLog());
	box->setWidth(st::boxWideWidth);
	box->setMaxHeight(st::boxMaxListHeight);
	const auto text = ReadLogTail();
	box->addRow(object_ptr<Ui::FlatLabel>(
		box,
		text.isEmpty() ? tr::ayu_PluginsLogEmpty(tr::now) : text,
		st::boxLabel))->setSelectable(true);
	if (!text.isEmpty()) {
		box->addButton(tr::ayu_PluginsLogCopy(), [=] {
			QGuiApplication::clipboard()->setText(text);
			box->showToast(tr::ayu_PluginsLogCopied(tr::now));
		});
	}
	box->addButton(tr::lng_close(), [=] {
		box->closeBox();
	});
}

void InputSettingBox(
		not_null<Ui::GenericBox*> box,
		const QString &title,
		const QString &value,
		bool multiline,
		Fn<void(QString)> done) {
	box->setTitle(rpl::single(title));
	const auto field = box->addRow(object_ptr<Ui::InputField>(
		box,
		st::defaultInputField,
		(multiline
			? Ui::InputField::Mode::MultiLine
			: Ui::InputField::Mode::SingleLine),
		rpl::single(title),
		value));
	box->setFocusCallback([=] {
		field->setFocusFast();
	});
	box->addButton(tr::lng_settings_save(), [=] {
		done(field->getLastText());
		box->closeBox();
	});
	box->addButton(tr::lng_cancel(), [=] {
		box->closeBox();
	});
}

void PluginSettingsBox(
		not_null<Ui::GenericBox*> box,
		not_null<Window::SessionController*> controller,
		const QString &id,
		const QString &name) {
	box->setTitle(rpl::single(name));
	box->setWidth(st::boxWideWidth);
	const auto container = box->verticalLayout();
	const auto items = AyuPlugins::settings(id);
	if (items.isEmpty()) {
		Ui::AddDividerText(container, tr::ayu_PluginNoSettings());
	}
	for (auto i = 0; i != items.size(); ++i) {
		const auto item = items[i].toObject();
		const auto type = item[u"type"_q].toString();
		const auto text = item[u"text"_q].toString();
		const auto key = item[u"key"_q].toString();
		if (type == u"header"_q) {
			Ui::AddSkip(container);
			Ui::AddSubsectionTitle(container, rpl::single(text));
		} else if (type == u"divider"_q) {
			if (text.isEmpty()) {
				Ui::AddDivider(container);
			} else {
				Ui::AddDividerText(container, rpl::single(text));
			}
		} else if (type == u"switch"_q) {
			AddButtonWithIcon(
				container,
				rpl::single(text),
				st::settingsButtonNoIcon
			)->toggleOn(
				rpl::single(item[u"value"_q].toBool())
			)->toggledChanges(
			) | rpl::on_next([=](bool value) {
				AyuPlugins::setSetting(id, key, value);
			}, container->lifetime());
		} else if (type == u"input"_q) {
			const auto value = container->lifetime().make_state<
				rpl::variable<QString>>(item[u"value"_q].toString());
			const auto multiline = item[u"multiline"_q].toBool();
			AddButtonWithLabel(
				container,
				rpl::single(text),
				value->value(),
				st::settingsButtonNoIcon
			)->setClickedCallback([=] {
				controller->show(Box(
					InputSettingBox,
					text,
					value->current(),
					multiline,
					[=](QString result) {
						*value = result;
						AyuPlugins::setSetting(id, key, result);
					}));
			});
		} else if (type == u"selector"_q) {
			auto options = std::vector<QString>();
			for (const auto &option : item[u"items"_q].toArray()) {
				options.push_back(option.toString());
			}
			const auto shared = std::make_shared<std::vector<QString>>(
				std::move(options));
			const auto selected = container->lifetime().make_state<
				rpl::variable<int>>(item[u"value"_q].toInt());
			AddButtonWithLabel(
				container,
				rpl::single(text),
				selected->value() | rpl::map([=](int index) {
					return (index >= 0 && index < int(shared->size()))
						? (*shared)[index]
						: QString();
				}),
				st::settingsButtonNoIcon
			)->setClickedCallback([=] {
				controller->show(Box([=](not_null<Ui::GenericBox*> choice) {
					SingleChoiceBox(choice, {
						.title = rpl::single(text),
						.options = *shared,
						.initialSelection = selected->current(),
						.callback = [=](int index) {
							*selected = index;
							AyuPlugins::setSetting(id, key, index);
						},
					});
				}));
			});
		} else if (type == u"text"_q) {
			const auto button = AddButtonWithIcon(
				container,
				rpl::single(text),
				(item[u"red"_q].toBool()
					? st::settingsAttentionButton
					: st::settingsButtonNoIcon));
			if (item[u"clickable"_q].toBool()) {
				button->setClickedCallback([=] {
					AyuPlugins::clickSetting(id, i);
				});
			}
		}
	}
	box->addButton(tr::lng_close(), [=] {
		box->closeBox();
	});
}

[[nodiscard]] QString LastLine(const QString &text) {
	const auto lines = text.split('\n', Qt::SkipEmptyParts);
	return lines.isEmpty() ? text : lines.back().trimmed();
}

void FillPluginsList(
		not_null<Ui::VerticalLayout*> list,
		not_null<Window::SessionController*> controller) {
	const auto plugins = AyuPlugins::list();
	if (plugins.empty()) {
		Ui::AddSkip(list);
		Ui::AddDividerText(list, tr::ayu_PluginsEmpty());
		return;
	}
	for (const auto &plugin : plugins) {
		const auto id = plugin.id;
		const auto name = plugin.name;
		Ui::AddSkip(list);
		AddButtonWithIcon(
			list,
			rpl::single(plugin.name + u" "_q + plugin.version),
			st::settingsButton,
			{ &st::menuIconCustomize }
		)->toggleOn(
			rpl::single(plugin.enabled)
		)->toggledChanges(
		) | rpl::on_next([=](bool enabled) {
			AyuPlugins::setEnabled(id, enabled);
		}, list->lifetime());
		if (plugin.enabled && plugin.hasSettings) {
			AddButtonWithIcon(
				list,
				tr::ayu_PluginSettings(),
				st::settingsButton,
				{ &st::menuIconSettings }
			)->setClickedCallback([=] {
				controller->show(Box(PluginSettingsBox, controller, id, name));
			});
		}
		AddButtonWithIcon(
			list,
			tr::ayu_PluginDelete(),
			st::settingsAttentionButtonWithIcon,
			{ &st::menuIconDelete }
		)->setClickedCallback([=] {
			controller->show(Ui::MakeConfirmBox({
				.text = tr::ayu_PluginDeleteConfirm(
					tr::now,
					lt_name,
					name),
				.confirmed = [=](Fn<void()> &&close) {
					AyuPlugins::uninstall(id);
					close();
				},
				.confirmText = tr::lng_box_delete(),
				.confirmStyle = &st::attentionBoxButton,
			}));
		});
		auto about = plugin.description;
		if (!plugin.author.isEmpty()) {
			about += (about.isEmpty() ? u""_q : u"\n"_q) + plugin.author;
		}
		if (!plugin.error.isEmpty()) {
			about += (about.isEmpty() ? u""_q : u"\n\n"_q)
				+ tr::ayu_PluginLoadError(
					tr::now,
					lt_error,
					LastLine(plugin.error));
		}
		Ui::AddSkip(list);
		if (!about.isEmpty()) {
			Ui::AddDividerText(list, rpl::single(about));
		} else {
			Ui::AddDivider(list);
		}
	}
}

} // namespace

AyuPluginsSection::AyuPluginsSection(
	QWidget *parent,
	not_null<Window::SessionController*> controller)
: Section(parent, controller) {
	setupContent();
}

rpl::producer<QString> AyuPluginsSection::title() {
	return tr::ayu_CategoryPlugins();
}

void AyuPluginsSection::setupContent() {
	const auto content = Ui::CreateChild<Ui::VerticalLayout>(this);
	const auto window = controller();

	Ui::AddSkip(content);
	if (!AyuPlugins::available()) {
		Ui::AddDividerText(content, tr::ayu_PluginsRuntimeMissing());
		Ui::AddSkip(content);
	}
	AddButtonWithIcon(
		content,
		tr::ayu_PluginsInstall(),
		st::settingsButton,
		{ &st::menuIconAdd }
	)->setClickedCallback([=] {
		FileDialog::GetOpenPath(
			this,
			tr::ayu_PluginsInstallTitle(tr::now),
			u"Plugins (*.plugin *.py)"_q,
			crl::guard(this, [=](const FileDialog::OpenResult &result) {
				if (!result.paths.isEmpty()) {
					InstallPluginWithToast(window, result.paths.front());
				}
			}));
	});
	AddButtonWithIcon(
		content,
		tr::ayu_PluginsOpenFolder(),
		st::settingsButton,
		{ &st::menuIconShowInFolder }
	)->setClickedCallback([=] {
		QDir().mkpath(AyuPlugins::pluginsPath());
		QDesktopServices::openUrl(
			QUrl::fromLocalFile(AyuPlugins::pluginsPath()));
	});
	AddButtonWithIcon(
		content,
		tr::ayu_PluginsLog(),
		st::settingsButton,
		{ &st::menuIconInfo }
	)->setClickedCallback([=] {
		window->show(Box(PluginsLogBox));
	});
	Ui::AddSkip(content);
	Ui::AddDividerText(content, tr::ayu_PluginsDescription());

	const auto list = content->add(object_ptr<Ui::VerticalLayout>(content));
	const auto refill = [=] {
		list->clear();
		FillPluginsList(list, window);
		list->resizeToWidth(content->width());
	};
	AyuPlugins::changes(
	) | rpl::on_next([=] {
		// Toggles fire from inside the list that is about to be rebuilt.
		crl::on_main(list, refill);
	}, list->lifetime());
	refill();

	Ui::ResizeFitChild(this, content);
}

Type AyuPluginsId() {
	return AyuPluginsSection::Id();
}

void InstallPluginWithToast(
		not_null<Window::SessionController*> controller,
		const QString &path) {
	const auto error = AyuPlugins::install(path);
	controller->showToast(error.isEmpty()
		? tr::ayu_PluginInstalled(tr::now)
		: tr::ayu_PluginInstallFailed(tr::now, lt_error, LastLine(error)));
}

} // namespace Settings
