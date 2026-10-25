// This is the source code of AyuGram for Desktop.
//
// We do not and cannot prevent the use of our code,
// but be respectful and credit the original author.
//
// Copyright @Radolyn, 2026
#pragma once

#include <QtCore/QJsonArray>

namespace Api {
struct MessageToSend;
} // namespace Api

namespace Main {
class Session;
} // namespace Main

namespace MTP {
class Instance;
struct Response;
namespace details {
class SerializedRequest;
} // namespace details
} // namespace MTP

namespace Ui {
class PopupMenu;
} // namespace Ui

class HistoryItem;

namespace AyuPlugins {

struct PluginInfo {
	QString id;
	QString name;
	QString description;
	QString author;
	QString version;
	QString error;
	bool enabled = false;
	bool hasSettings = false;
};

void init();
[[nodiscard]] bool available();
[[nodiscard]] QString pluginsPath();
[[nodiscard]] QString logPath();

[[nodiscard]] std::vector<PluginInfo> list();
[[nodiscard]] rpl::producer<> changes();
void setEnabled(const QString &id, bool enabled);
[[nodiscard]] QString install(const QString &path);
void uninstall(const QString &id);

[[nodiscard]] QJsonArray settings(const QString &id);
void setSetting(const QString &id, const QString &key, const QJsonValue &value);
void clickSetting(const QString &id, int index);

// Returns false when a plugin cancelled sending.
[[nodiscard]] bool onSendMessage(
	not_null<Main::Session*> session,
	Api::MessageToSend &message);
void onMessageCreated(not_null<HistoryItem*> item);
void fillMessageMenu(
	not_null<Ui::PopupMenu*> menu,
	not_null<HistoryItem*> item);

// Returns false when a plugin cancelled the request.
[[nodiscard]] bool onRequest(
	not_null<MTP::Instance*> instance,
	mtpRequestId requestId,
	MTP::details::SerializedRequest &request);
[[nodiscard]] std::optional<mtpBuffer> onResponse(
	not_null<MTP::Instance*> instance,
	const MTP::Response &response);

// An empty buffer means the updates were dropped.
[[nodiscard]] std::optional<mtpBuffer> onUpdates(
	not_null<MTP::Instance*> instance,
	const MTP::Response &message);

} // namespace AyuPlugins
