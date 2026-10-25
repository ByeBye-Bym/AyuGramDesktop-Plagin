# AyuGram Desktop Plagin (Ayuplagin)

<img src="Telegram/Resources/art/ayu/default/app.svg" width="128" alt="Ayuplagin">

**Ayuplagin** - это AyuGram Desktop для Windows, который умеет запускать плагины от [exteraGram](https://plugins.exteragram.app/docs).
Больше он ничем не отличается: режим призрака, история сообщений, антиудаление и всё остальное из AyuGram на месте.

> Это неофициальная сборка. Разработчики AyuGram и Telegram к ней отношения не имеют,
> поэтому с ошибками Ayuplagin приходите сюда, а не к ним.

## Как установить

1. Скачайте `Ayuplagin-<версия>-win64.zip` со страницы [Releases](https://github.com/ByeBye-Bym/AyuGramDesktop-Plagin/releases).
2. Распакуйте в любую папку, например в `C:\Ayuplagin`.
3. Запустите `Ayuplagin.exe`.

Нужна Windows 10 или 11 (64 бит). Ставить Python не надо, он уже лежит внутри, в папке `python\`.
На Windows 11 с ARM-процессором программа должна запуститься через эмуляцию, но мы это пока не проверяли.

Программа не подписана, поэтому при первом запуске Windows может испугаться и показать «Windows защитила ваш компьютер».
Это нормально: нажмите **Подробнее**, потом **Выполнить в любом случае**.
Если антивирус что-то удалил из папки `python\`, плагины работать перестанут. Тогда добавьте папку программы в исключения.

### Где хранятся данные

Всё (вход в аккаунт, кэш, плагины) лежит в папке `tdata` рядом с `Ayuplagin.exe`.
Если программа стоит там, куда нельзя писать (например, в `Program Files`), данные уйдут в `%APPDATA%\AyuGram Desktop Plagin`.
С обычным AyuGram ничего не пересекается, их можно держать рядом. Просто в Ayuplagin придётся войти в аккаунт отдельно.

> ⚠️ **Никому не отправляйте папку `tdata`.** По ней можно зайти в ваш аккаунт без пароля и кода.
> Если что-то сломалось, пришлите текст из журнала ошибок (как его достать, написано ниже), этого хватит.

**Как обновиться:** распакуйте новую версию прямо поверх старой. Папка `tdata` останется на месте, входить заново не придётся.

## Плагины

### Как поставить плагин

- Скиньте файл `.plugin` в любой чат (хоть в «Избранное»), нажмите на него и выберите **Установить**.
- Или зайдите в **Настройки → Плагины → Установить плагин** и выберите файл.

В том же разделе плагины можно включать, выключать, настраивать и удалять.

Где что лежит:

| Что | Где |
|---|---|
| Плагины | `tdata\ayu\plugins\` |
| Их настройки и данные | `tdata\ayu\plugins_data\` |
| Журнал ошибок | `tdata\ayu\plugins_data\plugins.log` |

### Если плагин не работает

Откройте **Настройки → Плагины → Журнал ошибок** и нажмите **Скопировать**. Вставьте этот текст в сообщение об ошибке.
По нему видно версию программы, Python и Windows, а также что именно пошло не так.

### Какие плагины подойдут

Ayuplagin тянет плагины, которые работают **с текстом и данными**. Вот что поддерживается:

- `BasePlugin`: загрузка и выгрузка, настройки (`get_setting` / `set_setting`), лог;
- `on_send_message_hook`: поменять или отменить сообщение перед отправкой;
- `add_hook` вместе с `pre_request_hook`, `post_request_hook`, `on_update_hook` и `on_updates_hook`: читать, менять и отменять запросы к Telegram (`TL_messages_sendMessage`, `TL_account_updateStatus` и другие) и входящие обновления (`TL_updateNewMessage` и другие);
- свои пункты в меню сообщения (`MenuItemType.MESSAGE_CONTEXT_MENU`);
- `ui.settings`: `Header`, `Divider`, `Switch`, `Selector`, `Input`, `EditText`, `Text`;
- `ui.alert.AlertDialogBuilder` и `ui.bulletin.BulletinHelper`;
- `client_utils`: `send_text`, `send_message`, `edit_message_local`, `get_message`, `run_on_queue`;
- `file_utils` и `android_utils` (`log`, `run_on_ui_thread`, `copy_to_clipboard`).

### Что не заработает

- Всё, что связано с интерфейсом Android и Java: свои экраны, `View`, перехват любых Java-методов.
  Исключение одно: перехват показа сообщения. Он нужен плагинам, которые правят сообщения у вас на экране.
- Пункты в других меню: боковом, меню чата, профиля.
- `pre_request_hook` видит запросы только тех аккаунтов, в которые вы вошли.
  `on_update_hook` видит обновления, которые сервер присылает сам, но не те, что программа догружает после переподключения.

Если плагин просит то, чего тут нет, он всё равно загрузится, просто эта его часть не сработает. В журнале ошибок при этом появится предупреждение.

### Перенести плагин с помощью ИИ

Если плагин не работает, его часто можно переделать под Ayuplagin с помощью ИИ: Claude, ChatGPT и т. п.
Скопируйте промт ниже (на GitHub справа от блока есть кнопка копирования), вставьте в чат, а в самый конец добавьте код плагина или приложите файл `.plugin`.
Если плагин всё равно падает, отправьте ИИ текст из журнала ошибок и попросите исправить.

```text
Ты помогаешь перенести плагин exteraGram (Telegram для Android) в Ayuplagin.
Ayuplagin - это Telegram-клиент для Windows на основе AyuGram Desktop. Он запускает плагины exteraGram во встроенном Python 3.11, но вместо Android и Java там только заглушки. Перепиши плагин так, чтобы он работал в Ayuplagin.

Что есть в Ayuplagin:
- base_plugin: BasePlugin (on_plugin_load, on_plugin_unload, on_app_event, create_settings, get_setting, set_setting, log, self.logger), HookResult, HookStrategy (DEFAULT, CANCEL, MODIFY, MODIFY_FINAL), MenuItemData, MenuItemType, MethodHook.
- add_on_send_message_hook + on_send_message_hook(account, params). У params есть только message, peer, replyToMsgId. Менять можно только текст, форматирование при изменении пропадает.
- add_hook(name, match_substring=False, priority=0) + pre_request_hook, post_request_hook, on_update_hook, on_updates_hook. Запросы и обновления приходят как Python-объекты по схеме Telegram API: имя класса вида TL_messages_sendMessage, поля называются как в api.tl (message, peer, random_id и т. д.), флаги считаются сами. Объект можно менять на месте и вернуть HookResult(strategy=HookStrategy.MODIFY, request=...). Ошибка в post_request_hook приходит как объект с полями code и text.
- add_menu_item: работает только MenuItemType.MESSAGE_CONTEXT_MENU. В on_click приходит словарь context с ключами account, dialog_id и message.
- MessageObject: getId(), getDialogId(), isOut(), getSenderId(), messageOwner.message, messageOwner.date, messageOwner.id, messageOwner.out.
- ui.settings: Header, Divider, Switch, Selector, Input, EditText, Text (с on_click, red, accent). Custom не поддерживается.
- ui.alert.AlertDialogBuilder: set_title, set_message, set_view, set_positive_button, set_negative_button, set_neutral_button, show, dismiss. В set_view понимаются только LinearLayout, TextView и EditText из android.widget.
- ui.bulletin.BulletinHelper: show_info, show_error, show_success (показывается как всплывающее уведомление).
- android.widget: EditText, TextView, LinearLayout, Toast. android.text.InputType. java.util.Calendar.
- client_utils: send_text(peer_id, text, replyToMsg=None), send_message({"peer", "message"}), edit_message_local(message_obj, text) (меняет текст только на этом компьютере), get_message(peer_id, msg_id), run_on_queue(fn), get_last_fragment().
- android_utils: log, run_on_ui_thread, copy_to_clipboard.
- file_utils: get_plugins_dir, get_cache_dir, get_files_dir, ensure_dir_exists, read_file, write_file, list_dir, delete_file.
- hook_utils.find_class + hook_all_methods работают только для "org.telegram.ui.Cells.ChatMessageCell" и метода "setMessageObject": хук вызывается, когда сообщение появляется в чате, param.args[0] - MessageObject.

Чего в Ayuplagin нет:
- Любых других классов Android и Java, jnius/Chaquopy, org.telegram.* (кроме перехвата выше), TLRPC из Java, свои экраны и View.
- Отправки своих запросов к API: send_request и похожего нет. Отправить можно только текст через send_text или send_message.
- Меню, кроме контекстного меню сообщения.
- Медиа, стикеров, файлов в сообщениях: работа идёт только с текстом и данными.

Правила:
1. Сохрани метаданные (__id__, __name__, __description__, __author__, __version__, __min_version__ и т. п.) и главную идею плагина.
2. Всё, что использует недоступное, замени на то, что есть в списке выше. Если замены нет, убери эту часть, а не оставляй вызов, который упадёт.
3. Не выдумывай функции, которых нет в списке.
4. Оберни рискованные места в try/except и пиши ошибки через self.logger.exception, чтобы они попадали в журнал ошибок Ayuplagin.
5. Ответ: сначала коротко по-русски, что поменял и что пришлось убрать. Потом весь файл .plugin целиком одним блоком кода, готовый для сохранения.

Вот плагин:
```

### Что хочется сделать дальше

Это планы, а не обещания: что получится и когда, пока не знаю.

- **Пункты в других меню.** В Telegram Desktop есть свои боковое меню, меню чата и меню профиля, так что плагины смогут добавлять кнопки и туда.
- **Больше элементов интерфейса.** Сейчас из Android-интерфейса понимаются только поля ввода и текст в диалогах. Хочу добавить кнопки, переключатели, списки и свои экраны в настройках плагина.
- **Перехват популярных Java-методов.** Плагины exteraGram часто подменяют одни и те же места Telegram для Android. Для тех, у которых есть аналог в Desktop, можно сделать такой же перехват, как уже сделан для показа сообщения.

Полностью Android и Java на компьютере не появятся. Плагины exteraGram могут дёргать любые классы Telegram для Android, а Desktop устроен совсем по-другому, и повторить их все нельзя. Поэтому плагины, которые рисуют свой интерфейс целиком на Android, скорее всего так и не заработают.

### ⚠️ Про безопасность

Плагин - это обычная программа на Python, и у неё **полный доступ к вашему аккаунту и файлам**.
Она может читать переписку, писать от вашего имени и копировать файлы с компьютера.
Ставьте плагины только из мест, которым доверяете, а лучше загляните в код перед установкой.

## Собрать самому

Всё как у AyuGram Desktop, по [инструкции для Windows x64](docs/building-win-x64.md).
Сверху понадобится Python 3.11 (x64): заголовки, `python311.lib`, `python311.dll`, `Lib\` и `DLLs\` положите в `Libraries\win64\python311`.
После сборки CMake сам скопирует Python и SDK плагинов в папку `python\` рядом с exe.

Для своей сборки возьмите собственные `api_id` и `api_hash` на [my.telegram.org](https://my.telegram.org).
Тестовые ключи из инструкции годятся только для себя, раздавать сборку с ними нельзя.

Тесты SDK плагинов можно гонять без сборки программы:

```
python Telegram/Resources/plugins_sdk_tests/run_tests.py
```

## Спасибо

- [AyuGram Desktop](https://github.com/AyuGram/AyuGramDesktop): Radolyn Labs и всем, кто его делает;
- [Telegram Desktop](https://github.com/telegramdesktop/tdesktop): команде Telegram;
- [exteraGram](https://exteragram.app): за формат плагинов и их API;
- [Material Icons](https://fonts.google.com/icons): за значок пазла (Apache 2.0).

## Лицензия

GNU GPL v3, как у AyuGram Desktop и Telegram Desktop. Подробности в [LICENSE](LICENSE) и [LEGAL](LEGAL).
