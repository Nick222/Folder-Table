# Folder Table

A plugin for **Zim Desktop Wiki** that displays notes located in the same folder as the current page as a customizable table.

Author: **Nick**

## Features

The plugin displays pages from the current folder in a table and allows sorting by any configured column.

Selecting a row opens the corresponding page in Zim. Values of type `url` are opened in the external browser.

Table settings are preserved between Zim sessions.

The configured columns, their order and data types, column widths, window size and position, and the last sort order are saved.

A **Reset settings** button restores the default column set.

## Menu

The **Tools** menu provides:

* **Folder table...** — open the table;
* **Configure table...** — configure the columns and their order.

## Data Sources

### Card

Fields in the form `Field: value` from the note card.

Built-in fields:

`Author`, `Title`, `Date`, `Publisher`, `Description`, `Content`, `ISBN`, `Place`, `Record`, `Copy`, `Source`, `Also`, `Notes`.

There is also a **Other field...** option for arbitrary card fields.

### Zim

* Note
* Path
* Modified
* Size
* Page characters — number of characters in the entire page

### Links

* Internal links
* External links
* Backlinks

### Objects

* Images
* Tables
* Objects

### Tasks

* Open tasks
* Scheduled

### Text

Fields from this source apply **only to the special level-2 section**:

```text
===== Text =====
```

The section continues until the next heading of the same level. Deeper headings remain part of the section.

Available fields:

* Has text
* Text beginning
* Words
* Lines
* Characters
* Full text

`Page characters` and `Text → Characters` are different values: the former counts characters in the whole page, while the latter counts characters only in the `===== Text =====` section.

## Data Types

* `text` — text
* `date` — date/time
* `number` — number
* `url` — URL opened in the browser
* `boolean` — logical value displayed as `Yes / No`

The data type determines how the column is sorted.

## Default Columns

By default:

* Note
* Modified
* Size
* Author

## Settings Storage

```text
~/.config/zim/folder_table.json
```

If `XDG_CONFIG_HOME` is set, the corresponding configuration directory is used.

## Installation

Create the directory:

```text
~/.local/share/zim/plugins/folder_table/
```

and place the plugin file there:

```text
__init__.py
```

Then enable **Folder Table** in Zim's plugin settings.

## Requirements

* Zim 0.77.x or a compatible version
* Python 3
* GTK 3 / PyGObject

The plugin uses standard Zim APIs for pages, the index, and ParseTree.

## Notes

A broken or unusual page should not stop the entire table from being built. Problematic values may simply appear empty.

The currently open page may use its current parsed tree, including unsaved changes. Other pages are analyzed independently from their stored contents.

## Resetting Settings

The **Reset settings** button restores the default columns and resets the saved window parameters, column widths, and sort order.

## License

MIT License.
