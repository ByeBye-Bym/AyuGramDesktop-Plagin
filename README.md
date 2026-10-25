# AyuGram Desktop Plagin (Ayuplagin)

<img src="Telegram/Resources/art/ayu/default/app.svg" width="128" alt="Ayuplagin">

**Ayuplagin** — неофициальный форк [AyuGram Desktop](https://github.com/AyuGram/AyuGramDesktop)
для Windows. Он добавляет одну возможность: запуск Python-плагинов в формате
[exteraGram](https://plugins.exteragram.app/docs).

Всё остальное работает как в AyuGram Desktop: режим призрака, история сообщений, антиудаление и прочие функции.

> Это не официальная сборка AyuGram и не официальный клиент Telegram.
> Об ошибках Ayuplagin сообщайте в этот репозиторий, а не разработчикам AyuGram или Telegram.

## Скачать

Готовые сборки лежат на вкладке [Releases](https://github.com/ByeBye-Bym/AyuGramDesktop-Plagin/releases).

1. Скачайте архив `Ayuplagin-<версия>-win64.zip`.
2. Распакуйте его в любую папку, например `C:\Ayuplagin`.
3. Запустите `Ayuplagin.exe`.

Требования: Windows 10 или 11, 64 бит. Python ставить не нужно, он уже лежит в папке `python\` рядом с программой.
На компьютерах с ARM-процессором Windows 11 запускает программу через встроенную эмуляцию x64. Этот вариант не проверялся.

У программы нет цифровой подписи, поэтому при первом запуске Windows может показать окно
«Windows защитила ваш компьютер». Нажмите **Подробнее → Выполнить в любом случае**.
Если антивирус удалил файлы из папки `python\`, плагины работать не будут. Добавьте папку программы в исключения.

Данные (вход в аккаунт, кэш, плагины) хранятся в папке `tdata` рядом с `Ayuplagin.exe`.
Если в папку программы нельзя ничего записать, например в `Program Files`, они хранятся в `%APPDATA%\AyuGram Desktop Plagin`.
С официальным AyuGram они не пересекаются: обе программы можно держать на одном компьютере, но в Ayuplagin нужно войти в аккаунт отдельно.

> ⚠️ **Никому не отправляйте папку `tdata`.** С ней можно войти в ваш аккаунт без пароля и кода.
> Для сообщения об ошибке достаточно текста из журнала ошибок (см. ниже).

**Обновление:** распакуйте новую версию поверх старой папки. Папка `tdata` при этом останется, и входить заново не придётся.

## Плагины

### Как установить плагин

- Отправьте файл `.plugin` в любой чат (например, в «Избранное»), нажмите на него и выберите **Установить**.
- Или откройте **Настройки → Плагины → Установить плагин** и выберите файл.

Там же плагины можно включать, выключать, удалять и настраивать.

Где лежат файлы:

| Что | Папка |
|---|---|
| Установленные плагины | `tdata\ayu\plugins\` |
| Настройки и данные плагинов | `tdata\ayu\plugins_data\` |
| Журнал ошибок | `tdata\ayu\plugins_data\plugins.log` |

Если плагин не работает, откройте **Настройки → Плагины → Журнал ошибок** и нажмите **Скопировать**.
Этот текст приложите к сообщению об ошибке: в нём видны версии программы, Python и Windows, а также ошибки плагинов.

### Что поддерживается

Ayuplagin запускает плагины exteraGram, которые работают **с текстом и данными**. Поддерживаются:

- `BasePlugin`: загрузка и выгрузка, настройки, `get_setting` / `set_setting`, логирование;
- `on_send_message_hook`: изменить или отменить отправку сообщения;
- `add_hook` с `pre_request_hook`, `post_request_hook`, `on_update_hook` и `on_updates_hook`: читать, изменять и отменять запросы Telegram API (`TL_messages_sendMessage`, `TL_account_updateStatus` и т. д.) и входящие обновления (`TL_updateNewMessage` и т. д.);
- пункты контекстного меню сообщения (`MenuItemType.MESSAGE_CONTEXT_MENU`);
- `ui.settings`: `Header`, `Divider`, `Switch`, `Selector`, `Input`, `EditText`, `Text`;
- `ui.alert.AlertDialogBuilder`, `ui.bulletin.BulletinHelper`;
- `client_utils`: `send_text`, `send_message`, `edit_message_local`, `get_message`, `run_on_queue`;
- `file_utils`, `android_utils` (`log`, `run_on_ui_thread`, `copy_to_clipboard`).

### Что не поддерживается

- Android-интерфейс и Java: свои экраны, `View`, перехват произвольных Java-методов. Работает только перехват создания сообщения, который нужен плагинам вроде `local_message_editor`.
- Пункты меню вне контекстного меню сообщения (боковое меню, меню чата, профиль).
- `pre_request_hook` видит запросы только залогиненных аккаунтов. `on_update_hook` видит обновления, которые сервер присылает сам, но не те, что приходят в ответ на `getDifference`.

Если плагин использует то, чего здесь нет, он загрузится, но эта часть просто не сработает: в `plugins.log` появится предупреждение.

### ⚠️ Безопасность

Плагин — это обычный код на Python с **полным доступом к вашему аккаунту и файлам на компьютере**.
Он может читать переписку, отправлять сообщения от вашего имени и копировать файлы.
Ставьте только плагины из источников, которым доверяете, и по возможности читайте их код перед установкой.

## Сборка из исходников

Сборка такая же, как у AyuGram Desktop, по [инструкции для Windows x64](docs/building-win-x64.md).
Дополнительно нужен Python 3.11 (x64) для встраивания: заголовки, `python311.lib`, `python311.dll`, `Lib\` и `DLLs\` должны лежать в
`Libraries\win64\python311`. После сборки CMake сам копирует его и SDK плагинов в папку `python\` рядом с exe.

Для своей сборки получите собственные `api_id` и `api_hash` на [my.telegram.org](https://my.telegram.org).
Тестовые ключи из инструкции нельзя использовать в сборках, которые вы раздаёте другим.

Тесты SDK плагинов запускаются без сборки программы:

```
python Telegram/Resources/plugins_sdk_tests/run_tests.py
```

## Благодарности

- [AyuGram Desktop](https://github.com/AyuGram/AyuGramDesktop) — Radolyn Labs и участники проекта;
- [Telegram Desktop](https://github.com/telegramdesktop/tdesktop) — команда Telegram;
- [exteraGram](https://exteragram.app) — формат плагинов и их API;
- значок пазла — [Material Icons](https://fonts.google.com/icons) (Apache 2.0).

## Лицензия

GNU GPL v3, как у AyuGram Desktop и Telegram Desktop: см. [LICENSE](LICENSE) и [LEGAL](LEGAL).
