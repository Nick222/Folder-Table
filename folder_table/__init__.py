# -*- coding: utf-8 -*-

import json
import os
import re
import sqlite3
import webbrowser
from datetime import datetime

from gi.repository import Gtk, Pango

from zim.plugins import PluginClass
from zim.actions import action
from zim.gui.mainwindow import MainWindowExtension
from zim.formats import HEADING
from zim.parse.links import is_wiki_link


class FolderTablePlugin(PluginClass):

    plugin_info = {
        'name': 'Folder Table',
        'description': 'Shows notes in the same folder as a sortable table.',
        'author': 'Nick',
    }


class FolderTableMainWindowExtension(MainWindowExtension):

    # -------------------------------------------------------------
    # Available data sources
    # -------------------------------------------------------------

    SOURCES = (
        'card',
        'zim',
        'links',
        'objects',
        'tasks',
        'text',
    )
    SOURCE_LABELS = {
        'card': 'Карточка',
        'zim': 'Zim',
        'links': 'Ссылки',
        'objects': 'Объекты',
        'tasks': 'Задачи',
        'text': 'Текст',
    }

    CARD_FIELDS = {
        'Автор': ('Автор', 'text'),
        'Название': ('Название', 'text'),
        'Дата': ('Дата', 'date'),
        'Публикатор': ('Публикатор', 'text'),
        'Описание': ('Описание', 'text'),
        'Содержание': ('Содержание', 'text'),
        'ISBN': ('ISBN', 'text'),
        'Место': ('Место', 'url'),
        'Запись': ('Запись', 'text'),
        'Копия': ('Копия', 'text'),
        'Источник': ('Источник', 'text'),
        'Также': ('Также', 'text'),
        'Примечания': ('Примечания', 'text'),
    }

    ZIM_FIELDS = {
        'name': ('Заметка', 'text'),
        'path': ('Путь', 'text'),
        'modified': ('Изменена', 'date'),
        'size': ('Размер', 'number'),
        'page_characters': ('Символы страницы', 'number'),
    }

    LINK_FIELDS = {
        'internal_links': ('Внутренние ссылки', 'number'),
        'external_links': ('Внешние ссылки', 'number'),
        'backlinks': ('Обратные ссылки', 'number'),
    }

    OBJECT_FIELDS = {
        'images': ('Изображения', 'number'),
        'tables': ('Таблицы', 'number'),
        'objects': ('Объекты', 'number'),
    }

    TASK_FIELDS = {
        'open_tasks': ('Открытые задачи', 'number'),
        'planned_tasks': ('Запланировано', 'text'),
    }

    TEXT_FIELDS = {
        'has_text': ('Есть текст', 'boolean'),
        'beginning': ('Начало текста', 'text'),
        'words': ('Слова', 'number'),
        'lines': ('Строки', 'number'),
        'characters': ('Символы', 'number'),
        'full_text': ('Полный текст', 'text'),
    }

    DEFAULT_COLUMNS = [
        {'source': 'zim', 'field': 'name', 'title': 'Заметка', 'type': 'text'},
        {'source': 'zim', 'field': 'modified', 'title': 'Изменена', 'type': 'date'},
        {'source': 'zim', 'field': 'size', 'title': 'Размер', 'type': 'number'},
        {'source': 'card', 'field': 'Автор', 'title': 'Автор', 'type': 'text'},
    ]

    COLUMN_TYPES = ('text', 'date', 'number', 'url', 'boolean')
    COLUMN_TYPE_LABELS = {
        'text': 'text',
        'date': 'date',
        'number': 'number',
        'url': 'url',
        'boolean': 'boolean',
    }

    DEFAULT_WINDOW = {
        'width': 900,
        'height': 450,
    }

    SETTINGS_DIR = os.path.join(
        os.environ.get(
            'XDG_CONFIG_HOME',
            os.path.expanduser('~/.config')
        ),
        'zim'
    )
    SETTINGS_FILE = os.path.join(
        SETTINGS_DIR,
        'folder_table.json'
    )

    # =============================================================
    # Main action
    # =============================================================

    @action('Таблица папки...', menuhints='tools')
    def show_folder_table(self):

        main_window = self.window

        # ---------------------------------------------------------
        # 1. Current notebook and page
        # ---------------------------------------------------------

        try:
            notebook = main_window.notebook
            page = main_window.page

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось получить текущую страницу Zim.\n\n'
                + str(e)
            )
            return

        if page is None:
            self._show_error(
                'Таблица папки',
                'Сейчас нет открытой страницы.'
            )
            return

        # ---------------------------------------------------------
        # 2. FilesLayout
        # ---------------------------------------------------------

        try:
            layout = notebook.index.layout

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось получить FilesLayout Zim.\n\n'
                + str(e)
            )
            return

        # ---------------------------------------------------------
        # 3. Get actual source file of current page
        # ---------------------------------------------------------

        try:
            mapped = layout.map_page(page)
            source_file = mapped[0]

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось определить файл текущей страницы.\n\n'
                + str(e)
            )
            return

        # ---------------------------------------------------------
        # 4. Convert absolute filesystem path to index path
        # ---------------------------------------------------------

        try:
            root_path = str(layout.root.path)
            source_path = str(source_file.path)

            if not source_path.startswith(root_path):
                raise RuntimeError(
                    'Файл страницы находится вне корня notebook.'
                )

            relative_path = source_path[
                len(root_path):
            ].lstrip('/')

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось определить путь страницы в индексе Zim.\n\n'
                + str(e)
            )
            return

        # ---------------------------------------------------------
        # 5. Open SQLite index
        # ---------------------------------------------------------

        dbpath = notebook.index.dbpath

        try:
            db = sqlite3.connect(dbpath)
            cursor = db.cursor()

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось открыть индекс Zim.\n\n'
                'Файл:\n'
                + str(dbpath)
                + '\n\n'
                + str(e)
            )
            return

        try:

            # -----------------------------------------------------
            # 6. Find current page in index
            # -----------------------------------------------------

            cursor.execute(
                """
                SELECT id, parent, path
                FROM files
                WHERE path = ?
                  AND node_type = ?
                """,
                (relative_path, 2)
            )

            current_record = cursor.fetchone()

            if current_record is None:
                self._show_error(
                    'Таблица папки',
                    'Текущая страница не найдена в индексе Zim.\n\n'
                    'Page.name:\n'
                    + str(page.name)
                    + '\n\n'
                    'Файловый путь:\n'
                    + str(relative_path)
                    + '\n\n'
                    'Index:\n'
                    + str(dbpath)
                )
                return

            current_id, parent_id, current_db_path = current_record

            current_page_record = cursor.execute(
                "SELECT id FROM pages WHERE name = ?",
                (page.name,)
            ).fetchone()
            current_page_id = (
                int(current_page_record[0])
                if current_page_record is not None
                else None
            )

            # -----------------------------------------------------
            # 7. Find all notes with the same parent
            # -----------------------------------------------------

            cursor.execute(
                """
                SELECT id, path
                FROM files
                WHERE parent = ?
                  AND node_type = ?
                ORDER BY path
                """,
                (parent_id, 2)
            )

            records = cursor.fetchall()

        except Exception as e:

            self._show_error(
                'Таблица папки',
                'Ошибка при чтении индекса Zim.\n\n'
                + str(e)
            )
            return

        finally:
            db.close()

        # ---------------------------------------------------------
        # 8. Fallback: current page itself
        # ---------------------------------------------------------

        if not records:
            records = [
                (current_id, current_db_path)
            ]

        # ---------------------------------------------------------
        # 9. Build rows
        # ---------------------------------------------------------

        rows = []

        for record_id, db_path in records:

            try:

                sibling_path = self._path_from_db_path(
                    db_path
                )

                if sibling_path is None:
                    continue

                sibling_page = notebook.get_page(
                    sibling_path
                )

                mapped = layout.map_page(
                    sibling_page
                )

                sibling_file = mapped[0]

                modified = sibling_page.mtime

                try:
                    size = int(sibling_file.size())

                except Exception:
                    try:
                        size = os.path.getsize(
                            sibling_file.path
                        )

                    except Exception:
                        size = 0

                display_name = sibling_page.basename

                if not display_name:
                    display_name = self._get_display_name(
                        db_path
                    )

                author = self._get_card_field(
                    sibling_file.path,
                    'Автор'
                )

                # The SQLite connection used for the folder query is
                # already closed here.  Resolve the page id through a
                # separate short-lived connection so every sibling page can
                # still be processed.
                page_id = self._get_page_id(sibling_path)

                rows.append({
                    'name': display_name,
                    'modified': self._format_mtime(modified),
                    'size': self._format_size(size),
                    'author': author,
                    '_path': sibling_path,
                    '_mtime': float(modified),
                    '_size': int(size),
                    '_id': int(record_id),
                    '_page_id': page_id,
                    '_file': sibling_file.path,
                    'path': str(sibling_path),
                })

            except Exception:
                # One broken/unusual page must not stop
                # the whole table.
                continue

        # ---------------------------------------------------------
        # 10. Final fallback
        # ---------------------------------------------------------

        if not rows:

            current_mtime = page.mtime

            try:
                current_size = int(
                    source_file.size()
                )

            except Exception:
                try:
                    current_size = os.path.getsize(
                        source_file.path
                    )

                except Exception:
                    current_size = 0

            current_author = self._get_card_field(
                source_file.path,
                'Автор'
            )

            rows.append({
                'name': page.basename,
                'modified': self._format_mtime(
                    current_mtime
                ),
                'size': self._format_size(
                    current_size
                ),
                'author': current_author,
                '_path': page,
                '_mtime': float(current_mtime),
                '_size': int(current_size),
                '_id': int(current_id),
                '_page_id': current_page_id,
                '_file': source_file.path,
                'path': str(page),
            })

        # ---------------------------------------------------------
        # 11. User-defined columns
        # ---------------------------------------------------------

        columns = self._load_columns()

        # Parse page content only when one of these sources is configured.
        if any(
            column.get('source') in ('links', 'objects', 'text')
            for column in columns
        ):
            for row in rows:
                self._prepare_page_analysis(row, layout)

        # Resolve all configured columns once per row. This keeps the
        # TreeView simple and also makes service fields inexpensive when
        # more than one row is displayed.
        for row in rows:
            for column in columns:
                storage_key = self._column_storage_key(column)
                row[storage_key] = self._get_column_value(
                    row,
                    column
                )

        # ---------------------------------------------------------
        # 12. Show result window
        # ---------------------------------------------------------

        self._show_window(
            main_window,
            rows,
            len(rows),
            columns
        )

    # =============================================================
    # Read one field from a card
    # =============================================================

    @staticmethod
    def _get_card_field(filename, field_name):

        if not filename:
            return ''

        try:
            with open(
                filename,
                'r',
                encoding='utf-8'
            ) as f:
                text = f.read()

        except Exception:
            return ''

        # Only spaces/tabs after the colon are allowed to be skipped.
        # A newline must end the field; it must never be swallowed by \s*.
        pattern = (
            r'^'
            + re.escape(field_name)
            + r':[ \t]*([^\r\n]*)$'
        )

        match = re.search(
            pattern,
            text,
            re.MULTILINE
        )

        if match is None:
            return ''

        return match.group(1).strip()

    # =============================================================
    # Convert database path to Zim Path
    # =============================================================

    @staticmethod
    def _path_from_db_path(db_path):

        if not db_path:
            return None

        if db_path.endswith('.txt'):
            db_path = db_path[:-4]

        parts = db_path.split('/')
        decoded_parts = []

        for part in parts:
            decoded_parts.append(
                part.replace('_', ' ')
            )

        from zim.notebook import Path
        return Path(':'.join(decoded_parts))

    # =============================================================
    # Display-name fallback
    # =============================================================

    @staticmethod
    def _get_display_name(path_string):

        if not path_string:
            return ''

        try:
            if path_string.endswith('.txt'):
                path_string = path_string[:-4]

            name = path_string.rsplit('/', 1)[-1]
            return name.replace('_', ' ')

        except Exception:
            return path_string

    # =============================================================
    # Date formatting
    # =============================================================

    @staticmethod
    def _format_mtime(mtime):

        if mtime is None:
            return ''

        try:
            return datetime.fromtimestamp(
                float(mtime)
            ).strftime(
                '%d.%m.%Y %H:%M'
            )

        except Exception:
            return str(mtime)

    # =============================================================
    # Size formatting
    # =============================================================

    @staticmethod
    def _format_size(size):

        if size is None:
            return ''

        try:
            size = int(size)

        except Exception:
            return ''

        if size < 1024:
            return '%d B' % size

        if size < 1024 * 1024:
            return '%.1f KB' % (
                size / 1024.0
            )

        if size < 1024 * 1024 * 1024:
            return '%.1f MB' % (
                size / (1024.0 * 1024.0)
            )

        return '%.1f GB' % (
            size / (1024.0 * 1024.0 * 1024.0)
        )

    # =============================================================
    # Settings
    # =============================================================

    @classmethod
    def _load_settings(cls):

        try:
            with open(
                cls.SETTINGS_FILE,
                'r',
                encoding='utf-8'
            ) as f:
                data = json.load(f)

            if isinstance(data, dict):
                return data

        except Exception:
            pass

        return {}

    @classmethod
    def _column_key(cls, source, field):
        return '%s\x00%s' % (source, field)

    @classmethod
    def _column_storage_key(cls, column):
        return cls._column_key(
            column.get('source', 'card'),
            column.get('field', '')
        )

    @classmethod
    def _infer_source(cls, field):
        if field in cls.ZIM_FIELDS:
            return 'zim'

        if field in cls.LINK_FIELDS:
            return 'links'

        if field in cls.OBJECT_FIELDS:
            return 'objects'

        if field in cls.TASK_FIELDS:
            return 'tasks'

        if field in cls.TEXT_FIELDS:
            return 'text'

        # Compatibility with the old internal field name.
        if field == 'author':
            return 'card'

        return 'card'

    @classmethod
    def _normalize_columns(cls, columns):

        result = []
        seen = set()

        if isinstance(columns, list):
            for item in columns:
                if not isinstance(item, dict):
                    continue

                field = str(item.get('field', '')).strip()
                if not field:
                    continue

                source = str(
                    item.get('source', '')
                ).strip()
                if source == 'service':
                    # Old "service" fields are now part of the Text source.
                    source = 'text'
                if source not in cls.SOURCES:
                    source = cls._infer_source(field)

                # Migrate the old special column name "author".
                if source == 'card' and field == 'author':
                    field = 'Автор'

                key = cls._column_key(source, field)
                if key in seen:
                    continue

                title = str(item.get('title', '')).strip()
                type_name = str(
                    item.get('type', '')
                ).strip()

                defaults = cls._field_defaults(
                    source,
                    field
                )

                if not title:
                    title = defaults[0] or field

                if type_name not in cls.COLUMN_TYPES:
                    type_name = defaults[1]

                result.append({
                    'source': source,
                    'field': field,
                    'title': title,
                    'type': type_name,
                })
                seen.add(key)

        name_key = cls._column_key('zim', 'name')

        if name_key not in seen:
            result.insert(
                0,
                {
                    'source': 'zim',
                    'field': 'name',
                    'title': 'Заметка',
                    'type': 'text',
                }
            )
        else:
            for item in result:
                if (
                    item['source'] == 'zim'
                    and item['field'] == 'name'
                ):
                    item['title'] = item['title'] or 'Заметка'
                    item['type'] = 'text'
                    break

        return result

    @classmethod
    def _field_defaults(cls, source, field):

        if source == 'card':
            return cls.CARD_FIELDS.get(
                field,
                (field, 'text')
            )

        if source == 'zim':
            return cls.ZIM_FIELDS.get(
                field,
                (field, 'text')
            )

        if source == 'links':
            return cls.LINK_FIELDS.get(
                field,
                (field, 'number')
            )

        if source == 'objects':
            return cls.OBJECT_FIELDS.get(
                field,
                (field, 'number')
            )

        if source == 'tasks':
            return cls.TASK_FIELDS.get(
                field,
                (field, 'number')
            )

        if source == 'text':
            return cls.TEXT_FIELDS.get(
                field,
                (field, 'text')
            )

        return field, 'text'

    @classmethod
    def _load_columns(cls):

        settings = cls._load_settings()
        columns = settings.get('columns')

        if not isinstance(columns, list) or not columns:
            return [dict(column) for column in cls.DEFAULT_COLUMNS]

        return cls._normalize_columns(columns)

    @classmethod
    def _save_settings(cls, **updates):

        settings = cls._load_settings()
        settings.update(updates)

        os.makedirs(
            cls.SETTINGS_DIR,
            exist_ok=True
        )

        temp_file = cls.SETTINGS_FILE + '.tmp'

        with open(
            temp_file,
            'w',
            encoding='utf-8'
        ) as f:
            json.dump(
                settings,
                f,
                ensure_ascii=False,
                indent=2
            )
            f.write('\n')

        os.replace(
            temp_file,
            cls.SETTINGS_FILE
        )

    @classmethod
    def _save_columns(cls, columns):
        cls._save_settings(
            columns=cls._normalize_columns(columns)
        )

    @classmethod
    def _load_widths(cls):

        settings = cls._load_settings()
        widths = settings.get('column_widths')

        if not isinstance(widths, dict):
            return {}

        result = {}
        for field, width in widths.items():
            try:
                width = int(width)
            except Exception:
                continue

            if width >= 40:
                result[str(field)] = width

        return result

    @classmethod
    def _load_window(cls):

        settings = cls._load_settings()
        window = settings.get('window')

        result = dict(cls.DEFAULT_WINDOW)

        if isinstance(window, dict):
            for key in ('width', 'height'):
                try:
                    value = int(window.get(key))
                    if value >= 300:
                        result[key] = value
                except Exception:
                    pass

            for key in ('x', 'y'):
                try:
                    result[key] = int(window.get(key))
                except Exception:
                    pass

        return result

    @classmethod
    def _load_sort(cls):

        settings = cls._load_settings()
        sort_data = settings.get('sort')

        if not isinstance(sort_data, dict):
            return None, Gtk.SortType.ASCENDING

        field = sort_data.get('field')
        order = sort_data.get('order', 'ascending')

        if order == 'descending':
            sort_type = Gtk.SortType.DESCENDING
        else:
            sort_type = Gtk.SortType.ASCENDING

        if not isinstance(field, str):
            field = None

        return field, sort_type

    @classmethod
    def _reset_settings(cls):
        cls._save_settings(
            columns=[dict(column) for column in cls.DEFAULT_COLUMNS],
            column_widths={},
            window=dict(cls.DEFAULT_WINDOW),
            sort={
                'field': 'name',
                'order': 'ascending',
            },
        )

    # =============================================================
    # Configuration action
    # =============================================================

    @action('Настроить таблицу...', menuhints='tools')
    def configure_table(self):

        dialog = Gtk.Dialog(
            title='Настройка таблицы папки',
            transient_for=self.window,
            modal=True
        )

        dialog.set_default_size(840, 480)

        content = dialog.get_content_area()
        content.set_border_width(8)

        model = Gtk.ListStore(
            str,  # source
            str,  # field
            str,  # title
            str,  # type
        )

        for column in self._load_columns():
            model.append((
                column['source'],
                column['field'],
                column['title'],
                column['type'],
            ))

        tree = Gtk.TreeView(model=model)
        tree.set_headers_clickable(True)
        tree.set_reorderable(False)

        headers = ('Источник', 'Поле', 'Заголовок', 'Тип')
        for index, title in enumerate(headers):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(
                title,
                renderer,
                text=index
            )
            column.set_resizable(True)
            tree.append_column(column)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(
            Gtk.PolicyType.AUTOMATIC,
            Gtk.PolicyType.AUTOMATIC
        )
        scrolled.set_min_content_height(240)
        scrolled.add(tree)
        content.pack_start(
            scrolled,
            True,
            True,
            0
        )

        hint = Gtk.Label(
            label=(
                'Карточка — поля вида «Поле: значение». '
                'Zim — данные самой заметки. Ссылки — внутренние, внешние '
                'и обратные ссылки. Объекты — изображения, таблицы и другие '
                'вставленные объекты. Задачи — данные индекса Task List.\n'
                'Текст — специальный раздел «===== Текст =====» и статистика '
                'его содержимого. Для произвольного поля карточки выберите '
                '«Другое поле...». Тип url открывает значение в браузере.'
            )
        )
        hint.set_xalign(0.0)
        hint.set_line_wrap(True)
        content.pack_start(
            hint,
            False,
            False,
            8
        )

        buttons_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )

        add_button = Gtk.Button(label='Добавить')
        edit_button = Gtk.Button(label='Изменить')
        up_button = Gtk.Button(label='Вверх')
        down_button = Gtk.Button(label='Вниз')
        delete_button = Gtk.Button(label='Удалить')
        reset_button = Gtk.Button(label='Сбросить настройки')

        for button in (
            add_button,
            edit_button,
            up_button,
            down_button,
            delete_button,
            reset_button,
        ):
            buttons_box.pack_start(
                button,
                False,
                False,
                0
            )

        content.pack_start(
            buttons_box,
            False,
            False,
            8
        )

        def get_selected_iter():
            selection = tree.get_selection()
            _model, treeiter = selection.get_selected()
            return treeiter

        def move_selected(delta):
            treeiter = get_selected_iter()
            if treeiter is None:
                return

            path = model.get_path(treeiter)
            index = path.get_indices()[0]
            new_index = index + delta

            if new_index < 0 or new_index >= len(model):
                return

            model.swap(
                treeiter,
                model.iter_nth_child(None, new_index)
            )

            tree.get_selection().select_path(
                model.get_path(treeiter)
            )

        def field_key(source, field):
            return self._column_key(source, field)

        def field_already_exists(source, field, except_iter=None):
            key = field_key(source, field)
            for row in model:
                if row.iter == except_iter:
                    continue
                existing_key = field_key(
                    str(row[0]),
                    str(row[1]).strip()
                )
                if existing_key == key:
                    return True
            return False

        def populate_field_combo(field_combo, source, selected_field=''):
            field_combo.remove_all()

            if source == 'card':
                for field, (title, _type_name) in self.CARD_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )
                field_combo.append(
                    '__custom__',
                    'Другое поле...'
                )
            elif source == 'zim':
                for field, (title, _type_name) in self.ZIM_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )
            elif source == 'links':
                for field, (title, _type_name) in self.LINK_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )
            elif source == 'objects':
                for field, (title, _type_name) in self.OBJECT_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )
            elif source == 'tasks':
                for field, (title, _type_name) in self.TASK_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )
            else:
                for field, (title, _type_name) in self.TEXT_FIELDS.items():
                    field_combo.append(
                        field,
                        field
                    )

            active_id = selected_field
            if source == 'card' and selected_field not in self.CARD_FIELDS:
                active_id = '__custom__'

            if field_combo.set_active_id(active_id):
                return

            field_combo.set_active(0)

        def update_type_from_field(type_combo, source, field):
            if not field or field == '__custom__':
                return

            _title, default_type = self._field_defaults(
                source,
                field
            )

            if default_type in self.COLUMN_TYPES:
                type_combo.set_active_id(default_type)

        def open_editor(treeiter=None):
            add_mode = treeiter is None

            editor = Gtk.Dialog(
                title=(
                    'Добавить поле'
                    if add_mode
                    else 'Изменить поле'
                ),
                transient_for=dialog,
                modal=True
            )

            editor.set_default_size(500, 300)

            box = editor.get_content_area()
            box.set_border_width(10)

            grid = Gtk.Grid()
            grid.set_row_spacing(8)
            grid.set_column_spacing(8)
            box.pack_start(grid, True, True, 0)

            source_combo = Gtk.ComboBoxText()
            for source in self.SOURCES:
                source_combo.append(
                    source,
                    self.SOURCE_LABELS[source]
                )

            field_combo = Gtk.ComboBoxText()
            custom_field_entry = Gtk.Entry()
            custom_field_entry.set_placeholder_text(
                'Имя поля, например: ISBN'
            )

            title_entry = Gtk.Entry()

            type_combo = Gtk.ComboBoxText()
            for type_name in self.COLUMN_TYPES:
                type_combo.append(
                    type_name,
                    self.COLUMN_TYPE_LABELS[type_name]
                )

            source = 'card'
            field = 'Автор'
            title = 'Автор'
            type_name = 'text'

            if treeiter is not None:
                source = str(model.get_value(treeiter, 0))
                field = str(model.get_value(treeiter, 1))
                title = str(model.get_value(treeiter, 2))
                type_name = str(model.get_value(treeiter, 3))

            if source not in self.SOURCES:
                source = self._infer_source(field)

            source_combo.set_active_id(source)
            populate_field_combo(
                field_combo,
                source,
                field
            )

            if source == 'card' and field not in self.CARD_FIELDS:
                custom_field_entry.set_text(field)
            else:
                custom_field_entry.set_text('')

            title_entry.set_text(title)

            if type_name not in self.COLUMN_TYPES:
                type_name = self._field_defaults(source, field)[1]
            type_combo.set_active_id(type_name)

            grid.attach(
                Gtk.Label(label='Источник:'), 0, 0, 1, 1
            )
            grid.attach(
                source_combo, 1, 0, 1, 1
            )
            grid.attach(
                Gtk.Label(label='Поле:'), 0, 1, 1, 1
            )
            grid.attach(
                field_combo, 1, 1, 1, 1
            )
            grid.attach(
                Gtk.Label(label='Своё поле:'), 0, 2, 1, 1
            )
            grid.attach(
                custom_field_entry, 1, 2, 1, 1
            )
            grid.attach(
                Gtk.Label(label='Заголовок:'), 0, 3, 1, 1
            )
            grid.attach(
                title_entry, 1, 3, 1, 1
            )
            grid.attach(
                Gtk.Label(label='Тип:'), 0, 4, 1, 1
            )
            grid.attach(
                type_combo, 1, 4, 1, 1
            )

            def sync_field_widgets(*_args):
                current_source = (
                    source_combo.get_active_id()
                    or 'card'
                )
                current_field = field_combo.get_active_id() or ''

                is_custom = (
                    current_source == 'card'
                    and current_field == '__custom__'
                )

                custom_field_entry.set_sensitive(is_custom)

                if not is_custom:
                    custom_field_entry.set_text('')
                    update_type_from_field(
                        type_combo,
                        current_source,
                        current_field
                    )

                    default_title = self._field_defaults(
                        current_source,
                        current_field
                    )[0]

                    if not title_entry.get_text().strip() or title_entry.get_text().strip() == default_title:
                        title_entry.set_text(default_title)

            def on_source_changed(*_args):
                current_source = (
                    source_combo.get_active_id()
                    or 'card'
                )
                populate_field_combo(
                    field_combo,
                    current_source
                )
                sync_field_widgets()

            def on_field_changed(*_args):
                sync_field_widgets()

            source_combo.connect(
                'changed',
                on_source_changed
            )
            field_combo.connect(
                'changed',
                on_field_changed
            )

            if field == 'name' and source == 'zim':
                source_combo.set_sensitive(False)
                field_combo.set_sensitive(False)
                custom_field_entry.set_sensitive(False)
                type_combo.set_sensitive(False)

            # Make the initial sensitivity match the current selection.
            sync_field_widgets()

            editor.add_button(
                'Отмена',
                Gtk.ResponseType.CANCEL
            )
            editor.add_button(
                'Сохранить',
                Gtk.ResponseType.OK
            )

            editor.show_all()
            response = editor.run()

            if response == Gtk.ResponseType.OK:
                final_source = (
                    source_combo.get_active_id()
                    or 'card'
                )
                selected_field = (
                    field_combo.get_active_id()
                    or ''
                )

                if (
                    final_source == 'card'
                    and selected_field == '__custom__'
                ):
                    final_field = (
                        custom_field_entry
                        .get_text()
                        .strip()
                    )
                else:
                    final_field = selected_field

                final_title = title_entry.get_text().strip()
                final_type = type_combo.get_active_id() or 'text'

                if not final_field:
                    self._show_error(
                        'Настройка таблицы',
                        'Поле не может быть пустым.'
                    )
                elif field_already_exists(
                    final_source,
                    final_field,
                    treeiter
                ):
                    self._show_error(
                        'Настройка таблицы',
                        'Такое сочетание источника и поля уже есть в таблице.'
                    )
                else:
                    default_title, default_type = self._field_defaults(
                        final_source,
                        final_field
                    )

                    if not final_title:
                        final_title = default_title or final_field

                    if final_type not in self.COLUMN_TYPES:
                        final_type = default_type

                    if add_mode:
                        model.append((
                            final_source,
                            final_field,
                            final_title,
                            final_type
                        ))
                    else:
                        model.set(
                            treeiter,
                            0, final_source,
                            1, final_field,
                            2, final_title,
                            3, final_type,
                        )

            editor.destroy()

        def on_add(_button):
            open_editor()

        def on_edit(_button):
            treeiter = get_selected_iter()
            if treeiter is not None:
                open_editor(treeiter)

        def on_delete(_button):
            treeiter = get_selected_iter()
            if treeiter is None:
                return

            source = str(model.get_value(treeiter, 0)).strip()
            field = str(model.get_value(treeiter, 1)).strip()

            if source == 'zim' and field == 'name':
                self._show_error(
                    'Настройка таблицы',
                    'Столбец «Заметка» удалить нельзя.'
                )
                return

            model.remove(treeiter)

        reset_requested = {'value': False}

        def on_reset(_button):
            model.clear()
            for column in self.DEFAULT_COLUMNS:
                model.append((
                    column['source'],
                    column['field'],
                    column['title'],
                    column['type'],
                ))
            reset_requested['value'] = True

        add_button.connect('clicked', on_add)
        edit_button.connect('clicked', on_edit)
        up_button.connect('clicked', lambda _b: move_selected(-1))
        down_button.connect('clicked', lambda _b: move_selected(1))
        delete_button.connect('clicked', on_delete)
        reset_button.connect('clicked', on_reset)

        dialog.add_button(
            'Отмена',
            Gtk.ResponseType.CANCEL
        )
        dialog.add_button(
            'Сохранить',
            Gtk.ResponseType.OK
        )

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            columns = []

            for row in model:
                source = str(row[0]).strip()
                field = str(row[1]).strip()
                title = str(row[2]).strip()
                type_name = str(row[3]).strip()

                if source not in self.SOURCES or not field:
                    continue

                default_title, default_type = self._field_defaults(
                    source,
                    field
                )

                if not title:
                    title = default_title or field

                if type_name not in self.COLUMN_TYPES:
                    type_name = default_type

                columns.append({
                    'source': source,
                    'field': field,
                    'title': title,
                    'type': type_name,
                })

            normalized = self._normalize_columns(columns)

            try:
                if reset_requested['value']:
                    self._reset_settings()
                else:
                    self._save_columns(normalized)
            except Exception as e:
                self._show_error(
                    'Настройка таблицы',
                    'Не удалось сохранить настройки.\n\n'
                    + str(e)
                )

        dialog.destroy()

    # =============================================================
    # Result window
    # =============================================================

    def _show_window(
        self,
        main_window,
        rows,
        count,
        columns
    ):

        dialog = Gtk.Dialog(
            title='Таблица папки',
            transient_for=main_window,
            modal=False
        )

        window_settings = self._load_window()
        dialog.set_default_size(
            window_settings['width'],
            window_settings['height']
        )

        if 'x' in window_settings and 'y' in window_settings:
            dialog.move(
                window_settings['x'],
                window_settings['y']
            )

        label = Gtk.Label()
        label.set_xalign(0.0)
        label.set_markup(
            '<b>Таблица папки</b>  (%d)' % count
        )

        model = Gtk.ListStore(
            *([str] * len(columns) + [object])
        )

        for row in rows:
            values = []

            for column in columns:
                values.append(
                    self._display_value(
                        row,
                        column
                    )
                )

            values.append(row['_path'])
            model.append(values)

        tree = Gtk.TreeView(model=model)
        tree.set_headers_clickable(True)
        tree.set_enable_search(True)

        width_settings = self._load_widths()
        tree_columns = []

        for index, column in enumerate(columns):
            renderer = Gtk.CellRendererText()

            if column['type'] == 'url':
                renderer.set_property(
                    'underline',
                    Pango.Underline.SINGLE
                )

            tree_column = Gtk.TreeViewColumn(
                column['title'],
                renderer,
                text=index
            )

            tree_column.set_sort_column_id(index)
            tree_column.set_resizable(True)

            if column['field'] == 'name':
                tree_column.set_expand(True)

            if column['field'] in width_settings:
                tree_column.set_fixed_width(
                    width_settings[column['field']]
                )
            elif column['field'] == 'name':
                tree_column.set_min_width(220)
            elif column['type'] == 'url':
                tree_column.set_min_width(220)

            model.set_sort_func(
                index,
                self._make_sort_func(
                    index,
                    column['type']
                )
            )

            tree_columns.append(tree_column)
            tree.append_column(tree_column)

        sort_field, sort_type = self._load_sort()
        sort_index = 0

        if sort_field:
            for index, column in enumerate(columns):
                if column['field'] == sort_field:
                    sort_index = index
                    break

        if columns:
            model.set_sort_column_id(
                sort_index,
                sort_type
            )

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(
            Gtk.PolicyType.AUTOMATIC,
            Gtk.PolicyType.AUTOMATIC
        )
        scrolled.add(tree)

        content = dialog.get_content_area()
        content.set_border_width(8)
        content.pack_start(
            label,
            False,
            False,
            6
        )
        content.pack_start(
            scrolled,
            True,
            True,
            0
        )

        selection = tree.get_selection()
        selection.connect(
            'changed',
            self._on_selection_changed,
            main_window
        )

        tree.connect(
            'button-press-event',
            self._on_tree_button_press,
            tree_columns,
            columns,
            main_window
        )

        dialog.add_button(
            'Закрыть',
            Gtk.ResponseType.CLOSE
        )

        def save_state_and_close(*_args):
            self._save_table_state(
                dialog,
                tree,
                tree_columns,
                columns,
                model
            )
            dialog.destroy()

        dialog.connect(
            'response',
            save_state_and_close
        )
        dialog.connect(
            'delete-event',
            lambda *_args: (
                save_state_and_close(),
                True
            )[1]
        )

        dialog.show_all()

    # =============================================================
    # Save result-window state
    # =============================================================

    def _save_table_state(
        self,
        dialog,
        tree,
        tree_columns,
        columns,
        model
    ):

        try:
            width, height = dialog.get_size()
            x, y = dialog.get_position()

            column_widths = {}
            for column, tree_column in zip(
                columns,
                tree_columns
            ):
                current_width = tree_column.get_width()
                if current_width >= 40:
                    column_widths[column['field']] = current_width

            sort_column_id, sort_type = (
                model.get_sort_column_id()
            )

            sort_field = None
            if 0 <= sort_column_id < len(columns):
                sort_field = columns[sort_column_id]['field']

            order = (
                'descending'
                if sort_type == Gtk.SortType.DESCENDING
                else 'ascending'
            )

            self._save_settings(
                column_widths=column_widths,
                window={
                    'width': int(width),
                    'height': int(height),
                    'x': int(x),
                    'y': int(y),
                },
                sort={
                    'field': sort_field,
                    'order': order,
                }
            )

        except Exception:
            # State saving must never prevent closing the window.
            pass

    # =============================================================
    # URL cell handler
    # =============================================================

    def _on_tree_button_press(
        self,
        tree,
        event,
        tree_columns,
        columns,
        _main_window
    ):

        if event.button != 1:
            return False

        try:
            result = tree.get_path_at_pos(
                int(event.x),
                int(event.y)
            )
        except Exception:
            return False

        if not result:
            return False

        path, clicked_column, _cell_x, _cell_y = result

        try:
            column_index = tree_columns.index(clicked_column)
        except ValueError:
            return False

        if column_index >= len(columns):
            return False

        if columns[column_index]['type'] != 'url':
            return False

        model = tree.get_model()
        treeiter = model.get_iter(path)
        value = model.get_value(
            treeiter,
            column_index
        )

        url = str(value or '').strip()
        if not url:
            return False

        if not self._is_url(url):
            return False

        self._opening_url = True

        try:
            tree.get_selection().select_path(path)
            webbrowser.open(url)
        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось открыть URL.\n\n'
                + url
                + '\n\n'
                + str(e)
            )
        finally:
            self._opening_url = False

        return True

    @staticmethod
    def _is_url(value):

        lowered = value.casefold()
        return lowered.startswith((
            'http://',
            'https://',
            'ftp://',
            'mailto:',
        ))

    # =============================================================
    # Display and sort values
    # =============================================================

    @classmethod
    def _make_sort_func(cls, column_index, type_name):

        def sort_func(model, iter1, iter2, _user_data=None):
            value1 = model.get_value(
                iter1,
                column_index
            )
            value2 = model.get_value(
                iter2,
                column_index
            )

            if type_name == 'number':
                a = cls._parse_number(value1)
                b = cls._parse_number(value2)

                if a is None and b is None:
                    return 0
                if a is None:
                    return -1
                if b is None:
                    return 1
                return (a > b) - (a < b)

            if type_name == 'date':
                a = cls._parse_date(value1)
                b = cls._parse_date(value2)

                if a is None and b is None:
                    return 0
                if a is None:
                    return -1
                if b is None:
                    return 1
                return (a > b) - (a < b)

            if type_name == 'boolean':
                def boolean_value(value):
                    text = '' if value is None else str(value).strip().casefold()
                    if text in ('да', 'yes', 'true', '1', 'on'):
                        return 1
                    if text in ('нет', 'no', 'false', '0', 'off', ''):
                        return 0
                    return 1 if text else 0

                a = boolean_value(value1)
                b = boolean_value(value2)
                return (a > b) - (a < b)

            a = '' if value1 is None else str(value1).casefold()
            b = '' if value2 is None else str(value2).casefold()

            return (a > b) - (a < b)

        return sort_func

    @staticmethod
    def _parse_number(value):

        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        normalized = (
            text
            .replace(' ', '')
            .replace(',', '.')
            .casefold()
        )

        match = re.search(
            r'[-+]?\d+(?:\.\d+)?',
            normalized
        )

        if match is None:
            return None

        try:
            number = float(match.group(0))
        except Exception:
            return None

        suffix = normalized[match.end():]

        multipliers = (
            ('tib', 1024 ** 4),
            ('tb', 1024 ** 4),
            ('gib', 1024 ** 3),
            ('gb', 1024 ** 3),
            ('mib', 1024 ** 2),
            ('mb', 1024 ** 2),
            ('kib', 1024),
            ('kb', 1024),
            ('b', 1),
        )

        for unit, multiplier in multipliers:
            if suffix.startswith(unit):
                return number * multiplier

        return number

    @staticmethod
    def _parse_date(value):

        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        formats = (
            '%d.%m.%Y %H:%M',
            '%d.%m.%Y',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
        )

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass

        return None

    def _get_column_value(self, row, column):

        source = column.get('source', 'card')
        field = column.get('field', '')

        if source == 'card':
            # Preserve compatibility with the old internal "author" name.
            if field == 'author':
                field = 'Автор'
            return self._get_card_field(
                row.get('_file'),
                field
            )

        if source == 'zim':
            if field == 'name':
                return row.get('name', '')
            if field == 'path':
                return row.get('path', '')
            if field == 'modified':
                return row.get('modified', '')
            if field == 'size':
                return row.get('size', '')
            if field == 'page_characters':
                return self._get_page_characters(row)
            return ''

        if source == 'links':
            analysis = self._get_page_analysis(row)
            if field == 'internal_links':
                return str(analysis['internal_links'])
            if field == 'external_links':
                return str(analysis['external_links'])
            if field == 'backlinks':
                return str(self._get_backlinks_count(row))
            return ''

        if source == 'objects':
            analysis = self._get_page_analysis(row)
            if field == 'images':
                return str(analysis['images'])
            if field == 'tables':
                return str(analysis['tables'])
            if field == 'objects':
                return str(analysis['objects'])
            return ''

        if source == 'tasks':
            return self._get_task_field(row, field)

        if source == 'text':
            text_data = self._get_text_section_data(row)
            if field == 'has_text':
                return 'Да' if text_data['has_text'] else 'Нет'
            if field == 'beginning':
                return text_data['beginning']
            if field == 'words':
                return str(text_data['words'])
            if field == 'lines':
                return str(text_data['lines'])
            if field == 'characters':
                return str(text_data['characters'])
            if field == 'full_text':
                return text_data['full_text']
            return ''

        return ''

    def _prepare_page_analysis(self, row, layout):
        if row.get('_page_analysis') is not None:
            return

        analysis = {
            'internal_links': 0,
            'external_links': 0,
            'images': 0,
            'tables': 0,
            'objects': 0,
        }
        tree = None
        raw_text = None

        try:
            notebook = self.window.notebook
            current_page = self.window.page
            row_path = row['_path']

            # For the page currently being edited, use its live ParseTree so
            # unsaved changes are included. For every sibling page, parse that
            # page's own source file directly. This avoids relying on whether
            # Zim happens to have that Page's ParseTree cached in memory.
            if (
                current_page is not None
                and row_path is not None
                and str(row_path) == str(current_page)
            ):
                tree = current_page.get_parsetree()
            else:
                sibling_page = notebook.get_page(row_path)
                mapped = layout.map_page(sibling_page)
                source_file = mapped[0]
                raw_text = source_file.read()
                if isinstance(raw_text, bytes):
                    raw_text = raw_text.decode(
                        'utf-8',
                        errors='replace'
                    )

                if raw_text is not None:
                    tree = sibling_page.format.Parser().parse(
                        raw_text,
                        file_input=True
                    )

            if tree is not None:
                root = tree._etree.getroot()

                for element in root.iter('link'):
                    href = element.attrib.get('href', '')
                    if not href:
                        continue
                    if is_wiki_link(href):
                        analysis['internal_links'] += 1
                    else:
                        analysis['external_links'] += 1

                analysis['images'] = sum(
                    1 for _ in root.iter('img')
                )
                analysis['tables'] = sum(
                    1 for _ in root.iter('table')
                )
                analysis['objects'] = sum(
                    1 for _ in root.iter('object')
                )

        except Exception:
            tree = None

        row['_page_analysis'] = analysis
        row['_text_section'] = (
            self._extract_text_section(tree)
            if tree is not None
            else None
        )

        row['_text_section_fallback'] = ''

        if tree is None:
            if raw_text is None:
                try:
                    mapped = layout.map_page(row['_path'])
                    source_file = mapped[0]
                    raw_text = source_file.read()
                    if isinstance(raw_text, bytes):
                        raw_text = raw_text.decode(
                            'utf-8',
                            errors='replace'
                        )
                except Exception:
                    raw_text = None

            if raw_text is not None:
                row['_text_section_fallback'] = (
                    self._extract_text_section_from_source(raw_text)
                )

    @staticmethod
    def _get_page_analysis(row):
        return row.get(
            '_page_analysis',
            {
                'internal_links': 0,
                'external_links': 0,
                'images': 0,
                'tables': 0,
                'objects': 0,
            }
        )

    def _get_text_section_data(self, row):
        cached = row.get('_text_data')
        if cached is not None:
            return cached

        # The statistics used to be calculated directly from the page text
        # and that worked reliably. Keep that simple approach here too:
        # first isolate the agreed Zim section ===== Текст =====, then
        # calculate words/lines/characters from its plain source text.
        section_text = None
        has_section = False

        filename = row.get('_file')
        if filename:
            try:
                with open(
                    filename,
                    'r',
                    encoding='utf-8'
                ) as f:
                    source_text = f.read()

            except Exception:
                source_text = None

            if source_text is not None:
                section_text = self._extract_text_section_from_source(
                    source_text
                )
                # An empty string can mean either an empty section or no
                # section. Check the heading explicitly.
                has_section = re.search(
                    r'^\s*={5}\s*Текст\s*={5}\s*$',
                    source_text,
                    re.IGNORECASE | re.MULTILINE
                ) is not None

        # For the currently edited page the source file can be older than
        # the live page. Use the ParseTree only when the source did not give
        # us a section, preserving unsaved edits in that special case.
        if not has_section:
            section_tokens = row.get('_text_section')
            if section_tokens is not None:
                section_text = self._tokens_to_text(section_tokens)
                has_section = True

        if section_text is None:
            section_text = ''

        text = section_text
        stripped = text.strip()

        data = {
            'has_section': has_section,
            'has_text': bool(stripped),
            'beginning': self._text_beginning(stripped),
            'words': len(re.findall(r'\S+', text)),
            'lines': len(text.splitlines()),
            'characters': len(text),
            'full_text': text.rstrip(),
        }
        row['_text_data'] = data
        return data

    @staticmethod
    def _text_beginning(text, limit=200):
        if not text:
            return ''
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + '…'

    @staticmethod
    def _tokens_to_text(tokens):
        return ''.join(
            token[1]
            for token in tokens
            if token and token[0] == 'T'
        )

    @classmethod
    def _extract_text_section(cls, tree):
        if tree is None:
            return None

        tokens = list(tree.iter_tokens())

        # ParseTree.iter_tokens() returns a flat stream. Find the first
        # level-2 heading named "Текст", then take everything after its
        # closing HEADING token up to the next level-2 heading. Nested
        # headings (level 3 and deeper) therefore remain part of the text.
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token[0] != HEADING:
                i += 1
                continue

            try:
                level = int(token[1].get('level'))
            except Exception:
                level = 0

            end = i + 1
            heading_tokens = []
            while end < len(tokens):
                current = tokens[end]
                if current == ('/', HEADING):
                    break
                heading_tokens.append(current)
                end += 1

            if level == 2:
                title = cls._tokens_to_text(
                    heading_tokens
                ).strip()

                if title.casefold() == 'текст':
                    content_start = end + 1

                    j = content_start
                    while j < len(tokens):
                        current = tokens[j]
                        if current[0] == HEADING:
                            try:
                                current_level = int(
                                    current[1].get('level')
                                )
                            except Exception:
                                current_level = 0

                            if current_level == 2:
                                return tokens[content_start:j]
                        j += 1

                    return tokens[content_start:]

            i = end + 1

        return None

    def _get_page_id(self, page_path):
        dbpath = getattr(self.window.notebook.index, 'dbpath', None)
        if not dbpath or page_path is None:
            return None

        try:
            db = sqlite3.connect(dbpath)
            try:
                record = db.execute(
                    'SELECT id FROM pages WHERE name=?',
                    (page_path.name,)
                ).fetchone()
            finally:
                db.close()

            if record is None:
                return None
            return int(record[0])
        except (sqlite3.Error, OSError, TypeError, ValueError):
            return None

    @staticmethod
    def _extract_text_section_from_source(source_text):
        if not source_text:
            return ''

        try:
            # Fallback for pages that cannot be parsed into a ParseTree.
            # The agreed special section is the level-2 heading:
            #     ===== Текст =====
            heading_re = re.compile(
                r'^\s*={5}\s+Текст\s+={5}\s*$',
                re.IGNORECASE | re.MULTILINE
            )
            next_heading_re = re.compile(
                r'^\s*={5}(?!={1,})[^\n]*={5}\s*$',
                re.MULTILINE
            )

            match = heading_re.search(source_text)
            if match is None:
                return ''

            start = match.end()
            next_match = next_heading_re.search(
                source_text,
                start
            )

            if next_match is None:
                section = source_text[start:]
            else:
                section = source_text[start:next_match.start()]

            return section.strip('\r\n')
        except Exception:
            return ''

    def _get_page_characters(self, row):
        cached = row.get('_page_characters')
        if cached is not None:
            return str(cached)

        text = row.get('_content')

        if text is None:
            filename = row.get('_file')
            if filename:
                try:
                    with open(
                        filename,
                        'r',
                        encoding='utf-8'
                    ) as f:
                        text = f.read()
                except Exception:
                    text = ''
            else:
                text = ''

            row['_content'] = text

        row['_page_characters'] = len(text)
        return str(row['_page_characters'])

    def _get_backlinks_count(self, row):
        if '_backlinks_count' in row:
            return row['_backlinks_count']

        page_id = row.get('_page_id')
        if not page_id:
            row['_backlinks_count'] = 0
            return 0

        dbpath = getattr(self.window.notebook.index, 'dbpath', None)
        if not dbpath:
            row['_backlinks_count'] = 0
            return 0

        try:
            db = sqlite3.connect(dbpath)
            try:
                result = db.execute(
                    'SELECT COUNT(*) FROM links WHERE target=? AND source<>?',
                    (int(page_id), 1)
                ).fetchone()
                count = int(result[0])
            finally:
                db.close()
        except Exception:
            count = 0

        row['_backlinks_count'] = count
        return count

    def _get_task_field(self, row, field):
        cached = row.get('_task_counts')
        if cached is None:
            cached = {
                'open_tasks': 0,
                'planned_tasks': False,
            }
            row['_task_counts'] = cached

        if field == 'planned_tasks':
            if cached.get('_loaded'):
                return 'Да' if cached['planned_tasks'] else 'Нет'
        elif field == 'open_tasks':
            if cached.get('_loaded'):
                return str(cached['open_tasks'])
        else:
            return '0'

        page_id = row.get('_page_id')
        if not page_id:
            cached['_loaded'] = True
            if field == 'planned_tasks':
                return 'Да' if cached['planned_tasks'] else 'Нет'
            return str(cached['open_tasks'])

        dbpath = getattr(self.window.notebook.index, 'dbpath', None)
        if not dbpath:
            cached['_loaded'] = True
            if field == 'planned_tasks':
                return 'Да' if cached['planned_tasks'] else 'Нет'
            return str(cached['open_tasks'])

        try:
            db = sqlite3.connect(dbpath)
            try:
                db.execute('SELECT 1 FROM tasklist LIMIT 1').fetchone()
                today = datetime.now().date().isoformat()

                result = db.execute(
                    'SELECT COUNT(*) FROM tasklist '
                    'WHERE source=? AND status=0',
                    (int(page_id),)
                ).fetchone()
                cached['open_tasks'] = int(result[0])

                result = db.execute(
                    'SELECT COUNT(*) FROM tasklist '
                    'WHERE source=? AND status=0 '
                    'AND (waiting=1 OR start>?)',
                    (int(page_id), today)
                ).fetchone()
                cached['planned_tasks'] = int(result[0]) > 0

            finally:
                db.close()
        except (sqlite3.Error, OSError):
            pass

        cached['_loaded'] = True
        if field == 'planned_tasks':
            return 'Да' if cached['planned_tasks'] else 'Нет'
        return str(cached['open_tasks'])

    @staticmethod
    def _display_value(row, column):
        key = FolderTableMainWindowExtension._column_storage_key(column)
        value = row.get(key, '')
        if value is None:
            return ''
        return str(value)

    # =============================================================
    # Single-click handler
    # =============================================================

    def _on_selection_changed(
        self,
        selection,
        main_window
    ):

        if getattr(self, '_opening_url', False):
            return

        model, treeiter = selection.get_selected()

        if treeiter is None:
            return

        try:
            path_index = model.get_n_columns() - 1
            page_path = model.get_value(
                treeiter,
                path_index
            )

        except Exception:
            return

        if page_path is None:
            return

        try:
            main_window.open_page(page_path)

        except Exception as e:
            self._show_error(
                'Таблица папки',
                'Не удалось открыть страницу.\n\n'
                + str(page_path)
                + '\n\n'
                + str(e)
            )

    # =============================================================
    # Dialog close
    # =============================================================

    @staticmethod
    def _on_dialog_response(dialog, response_id):
        dialog.destroy()

    # =============================================================
    # Error dialog
    # =============================================================

    def _show_error(self, title, message):

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )

        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
