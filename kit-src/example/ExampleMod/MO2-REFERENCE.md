# MO2 reference

What Mod Organizer 2 does with the one feature this plugin touches - a tool in the Tools menu - read at the release tag
before the plugin was written, and how Example Mod follows it (the pipeline's rule: read MO2's own implementation
first; gate rule `mo2-plugin-documents-mo2s-own-implementation`).

MO2 version read: **2.5.2** (tag `v2.5.2`).

Sources read:
- [src/mainwindow.cpp at v2.5.2](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/mainwindow.cpp) -
  `MainWindow::updateToolMenu` and `MainWindow::registerPluginTool`.

## What MO2 does

| Step | MO2 2.5.2 |
|---|---|
| Collect | `updateToolMenu` takes every loaded `IPluginTool`, sorts them by `displayName()` (case-insensitive) and drops the disabled ones. |
| Group | A `displayName()` containing `/` is split: the part before the first `/` names a submenu, and a submenu is only created when two or more tools share it. |
| Register | `registerPluginTool` makes a `QAction` from `icon()`, the name and `tooltip()`, calls `setParentWidget(this)` on the tool, and connects `triggered` to `display()` through a **queued** connection. |
| Errors | An exception thrown from `display()` is caught and shown as `Plugin "<localizedName>" failed: <what>`. |

## What Example Mod does, and how it follows MO2

| Example Mod | Follows MO2 by |
|---|---|
| `displayName()` returns "Example Mod", no `/` | appearing as a top-level entry of the Tools menu, sorted with the others |
| `icon()` returns an empty `QIcon`, `tooltip()` a sentence | giving MO2 the two things `registerPluginTool` puts on the action |
| `display()` shows one `QMessageBox` and returns | doing its work inside `display()`, the call MO2 queues and guards |
| no work in `init()` beyond keeping the organizer | leaving everything to the moment MO2 invokes the tool |

## Departures to revisit

- None. A real plugin that adds a parent widget, settings or a submenu should read the matching MO2 code again
  (`IPlugin::settings` handling in `src/plugincontainer.cpp`) and extend this file.
