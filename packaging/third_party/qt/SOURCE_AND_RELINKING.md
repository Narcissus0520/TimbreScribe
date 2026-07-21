# Qt / PySide6 source and relinking information

TimbreScribe distributes dynamically linked Qt 6 libraries through Qt for Python 6.11.1.
The selected community distribution is used under LGPL-3.0-only (or, where an individual
Qt module states otherwise, its applicable open-source terms). The complete LGPL-3.0 text is
included as `licenses/LGPL-3.0.txt`; the artifact inventory records every installed PySide6,
Shiboken6, and Qt for Python distribution.

Corresponding source for the exact Qt for Python 6.11.1 release is available from
<https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.1>. Qt module source archives are
available from <https://download.qt.io/official_releases/qt/6.11/6.11.1/submodules/>. Build and
installation documentation is at <https://doc.qt.io/qtforpython-6/building_from_source/>.

The libraries remain separate DLLs in the application's `_internal/PySide6` directory. A user
may replace those DLLs with a compatible, modified build for relinking and reverse-engineering
for debugging those modifications, subject to the LGPL and the technical ABI constraints of
Qt/PySide6. Keep a backup: an incompatible replacement can prevent the application from starting.

TimbreScribe itself is licensed under Apache-2.0. No commercial Qt license is conveyed by this
artifact. This notice is engineering evidence and not legal advice.
