"""The rail: a file tree that shows one level at a time.

**Show the repository. Let the reader choose what to open.** The version this
replaces listed every module it could find with its path flattened into the
row — `examples/account-baseline/`, `modules/cognito-user-pool/` as peers, each
with its files under it. On a real repository that is 63 rows of flattened path
and 273 files: the hierarchy is gone, and the top of the tree is below the fold
before anybody has read it. It was a search result dump wearing a tree's
clothes.

The mechanism is `Gtk.TreeListModel`, and it is the whole reason this is
affordable. It asks for a directory's children **only when that directory is
expanded**, and `Gtk.ListView` under it recycles rows, so a repository of any
size costs what has been opened rather than what exists.

One rule for the pointer, and it is worth stating because it is the one thing
people get wrong about trees: **the chevron and the name do the same thing.**
Clicking a folder — anywhere on the row — opens or closes it. Clicking a file
opens the file. Nobody has to hit a nine-pixel triangle.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from backsight.engine.layout.tree import Entry, ancestors, children, has_children


class Node(GObject.Object):
    """One row, as a thing a list model can hold."""

    __gtype_name__ = "BacksightTreeNode"

    def __init__(self, entry: Entry) -> None:
        super().__init__()
        self.entry = entry

    @property
    def path(self) -> Path:
        return self.entry.path


class FileTree(Gtk.ScrolledWindow):
    """Every file in the workspace, and none of them until they are asked for."""

    def __init__(
        self,
        *,
        on_open: Callable[[Path, int], None] | None = None,
        on_menu: Callable[[Path, bool], Gio.MenuModel] | None = None,
    ) -> None:
        super().__init__()
        self._on_open = on_open
        self._on_menu = on_menu
        self._root: Path | None = None
        self._model: Gtk.TreeListModel | None = None
        # Every row on screen right now, so a mark can be put on one without
        # rebuilding the tree and losing what somebody has opened.
        self.rows: dict[Path, tuple[Gtk.Widget, Gtk.Label]] = {}
        self._statuses: dict[Path, object] = {}
        self._marks: Callable[[Path, bool], tuple[str, str]] | None = None
        self._current: Path | None = None

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        factory.connect("unbind", self._unbind)

        self._list = Gtk.ListView(factory=factory)
        self._list.add_css_class("tf-tree")
        self._list.set_single_click_activate(True)
        self._list.connect("activate", self._activated)
        # **A double click is its own gesture.** A single-click-activate list
        # only activates on the first press of a click sequence, so the second
        # press of a quick double click never reached `activate` and a double
        # click read as one click. The toolkit's own press count decides here.
        doubled = Gtk.GestureClick(button=1)
        doubled.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        doubled.connect("pressed", self._pressed)
        self._list.add_controller(doubled)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_child(self._list)
        self.set_vexpand(True)

    # --- what is in it ------------------------------------------------------

    def show(self, root: Path | None) -> None:
        """Points the tree at a workspace. **Only its immediate children.**"""
        self._root = root
        self.rows.clear()
        if root is None:
            self._model = None
            self._list.set_model(None)
            return
        self._model = Gtk.TreeListModel.new(_store(children(root)), False, False, self._children_of)
        selection = Gtk.SingleSelection(model=self._model, autoselect=False, can_unselect=True)
        # Nothing is selected until somebody selects something. A tree that
        # highlights its first row on open is claiming you are somewhere.
        selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self._list.set_model(selection)

    def _children_of(self, item: GObject.Object) -> Gio.ListModel | None:
        """What one directory holds. **Called when it is expanded, and not before.**

        Returning `None` for a file is what tells the tree it has no chevron —
        and returning `None` for an empty directory is what stops one offering
        a chevron that reveals nothing.
        """
        node = item if isinstance(item, Node) else None
        if node is None or not node.entry.is_dir:
            return None
        if not has_children(node.path):
            return None
        return _store(children(node.path))

    # --- getting somewhere --------------------------------------------------

    def reveal(self, path: Path) -> None:
        """Opens the ancestors of one file, and **nothing else**.

        Walking down from the root, expanding each directory on the way and
        then looking inside it for the next — because a row's children do not
        exist until its own row has been expanded.
        """
        if self._model is None or self._root is None:
            return
        wanted = Path(path).resolve()
        for directory in [*ancestors(wanted, self._root), wanted]:
            row = self._row_for(directory)
            if row is None:
                return
            if directory != wanted:
                row.set_expanded(True)
        self._select(wanted)

    def _row_for(self, path: Path) -> Gtk.TreeListRow | None:
        """The row for a path, among the rows that are currently on the tree."""
        if self._model is None:
            return None
        for at in range(self._model.get_n_items()):
            row = self._model.get_row(at)
            if row is not None and row.get_item().path.resolve() == path:
                return row
        return None

    def _select(self, path: Path) -> None:
        selection = self._list.get_model()
        if self._model is None or selection is None:
            return
        for at in range(self._model.get_n_items()):
            row = self._model.get_row(at)
            if row is not None and row.get_item().path.resolve() == path:
                selection.set_selected(at)
                self._list.scroll_to(at, Gtk.ListScrollFlags.NONE, None)
                return

    def mark_current(self, path: Path | None) -> None:
        """Which file is in front, marked in the tree."""
        self._current = Path(path).resolve() if path is not None else None
        for where, (row, _mark) in self.rows.items():
            row.remove_css_class("tf-current")
            if where == self._current:
                row.add_css_class("tf-current")

    def marks_from(self, marks: Callable[[Path, bool], tuple[str, str]]) -> None:
        """Where the tree asks what to put on the right of a row, and how to
        colour its left edge. Asked per row as it is drawn, so a plan that
        finishes does not rebuild the tree."""
        self._marks = marks

    def remark(self) -> None:
        """Re-asks for every row on screen. Nothing is rebuilt and nothing that
        was opened closes."""
        for path, (row, mark) in self.rows.items():
            self._dress(row, mark, path)

    # --- drawing ------------------------------------------------------------

    def _setup(self, _factory, item: Gtk.ListItem) -> None:
        name = Gtk.Label(xalign=0.0, hexpand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        name.add_css_class("tf-tree-name")
        mark = Gtk.Label(xalign=1.0)
        mark.add_css_class("tf-micro")
        mark.add_css_class("tf-faint")
        beside = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        beside.append(name)
        beside.append(mark)

        expander = Gtk.TreeExpander()
        expander.set_indent_for_depth(True)
        # **A file reserves the chevron's width even though it has none.**
        # Without it a file three deep sits at the same x as a folder two deep,
        # because the folder's chevron makes up the difference — so the one
        # thing indentation is for, saying which level you are on, was wrong on
        # every row that had a file above it.
        expander.set_indent_for_icon(True)
        expander.set_child(beside)
        item.set_child(expander)

    def _bind(self, _factory, item: Gtk.ListItem) -> None:
        row = item.get_item()
        expander = item.get_child()
        expander.set_list_row(row)
        node = row.get_item()
        beside = expander.get_child()
        name, mark = beside.get_first_child(), beside.get_last_child()
        name.set_text(node.entry.shown)
        # Said out loud, because "network" and "network.tf" sound identical and
        # a trailing slash is not read.
        expander.update_property([Gtk.AccessibleProperty.LABEL], [node.entry.described])
        beside.add_css_class("tf-tree-row" if not node.entry.is_dir else "tf-tree-folder")
        self.rows[node.path.resolve()] = (beside, mark)
        self._dress(beside, mark, node.path.resolve())

    def _unbind(self, _factory, item: Gtk.ListItem) -> None:
        row = item.get_item()
        if row is not None and row.get_item() is not None:
            self.rows.pop(row.get_item().path.resolve(), None)

    def _dress(self, row: Gtk.Widget, mark: Gtk.Label, path: Path) -> None:
        """What git and the plan say about one row, on its two edges."""
        for old in ("tf-git-changed", "tf-git-added", "tf-git-untracked", "tf-current"):
            row.remove_css_class(old)
        if path == self._current:
            row.add_css_class("tf-current")
        if self._marks is None:
            mark.set_visible(False)
            return
        said, edge = self._marks(path, path.is_dir())
        mark.set_text(said)
        mark.set_visible(bool(said))
        if edge:
            row.add_css_class(edge)

    # --- the pointer --------------------------------------------------------

    def _activated(self, _view, position: int) -> None:
        """**A folder opens or closes; a file opens.** One rule, and the whole
        row is the target — nobody should have to hit a nine-pixel triangle."""
        if self._model is None:
            return
        row = self._model.get_row(position)
        if row is None:
            return
        node = row.get_item()
        if node.entry.is_dir:
            row.set_expanded(not row.get_expanded())
            return
        if self._on_open is not None:
            self._on_open(node.path, 1)

    def _pressed(self, _gesture, presses: int, x: float, y: float) -> None:
        """The second press of a double click on a file: keep it."""
        if presses != 2 or self._on_open is None:
            return
        found = self.path_at(x, y, relative_to=self._list)
        if found is not None and not found[1]:
            self._on_open(found[0], 2)

    def path_at(
        self, x: float, y: float, *, relative_to: Gtk.Widget | None = None
    ) -> tuple[Path, bool] | None:
        """Which row a point is on. The point is in this widget's coordinates
        unless `relative_to` names the widget it was measured against."""
        against = relative_to or self
        for path, (row, _mark) in self.rows.items():
            found, box = row.compute_bounds(against)
            if found and box.origin.y <= y <= box.origin.y + box.size.height:
                return path, path.is_dir()
        return None


def _store(entries: list[Entry]) -> Gio.ListStore:
    store = Gio.ListStore(item_type=Node)
    for entry in entries:
        store.append(Node(entry))
    return store


def install_menus(tree: FileTree, on_menu: Callable[[Path, bool], Gio.MenuModel]) -> None:
    """A right-click on a row, asking whoever owns the menus what belongs on it."""
    gesture = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)

    def pressed(_gesture, _presses: int, x: float, y: float) -> None:
        found = tree.path_at(x, y)
        if found is None:
            return
        popover = Gtk.PopoverMenu.new_from_model(on_menu(*found))
        popover.set_parent(tree)
        popover.set_has_arrow(False)
        # **Built empty and assigned.** A PyGObject boxed struct constructed
        # with arguments discards them and hands back a zeroed one, so a menu
        # pointed at `Gdk.Rectangle(x=…, y=…)` opens at the top-left corner
        # wherever it was clicked — silently, with a warning nobody reads.
        where = Gdk.Rectangle()
        where.x, where.y, where.width, where.height = int(x), int(y), 1, 1
        popover.set_pointing_to(where)
        popover.connect("closed", lambda one: GLib.idle_add(one.unparent))
        popover.popup()

    gesture.connect("pressed", pressed)
    tree.add_controller(gesture)
