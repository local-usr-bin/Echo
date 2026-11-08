# 第三方依赖与许可说明

Echo项目代码采用根目录[LICENSE](LICENSE)中的MIT条款，Copyright (c) 2026 local-usr-bin。下列外部组件不因此改为MIT。

本源码候选不捆绑第三方源码、DLL、字体、Python/Conda环境或安装包；依赖由使用者独立安装，保留其发行包内原有版权、许可及NOTICE。此表记录核验环境，版本文件不是完整平台构建锁。

| 外部组件 | 核验版本 | 许可/来源说明 |
|---|---|---|
| Python / 标准库 | 3.12.16 | [PSF-2.0及所含历史/组件许可](https://docs.python.org/3.12/license.html) |
| Tcl / Tk | 8.6.15 | [Tcl/Tk许可](https://www.tcl-lang.org/software/tcltk/license.html)，与tkinter Python接口分层 |
| NumPy | 2.3.5 | [主体BSD-3-Clause](https://numpy.org/doc/2.3/license.html)；安装构建的bundled notices另有条款 |
| Matplotlib | 3.10.8 | [Matplotlib自身PSF派生许可](https://matplotlib.org/3.10.8/project/license.html)，不是统一MIT；字体/其他附带资源独立 |
| Pillow | 13.0.0 | [主体MIT-CMU](https://pillow.readthedocs.io/en/stable/about.html)；附带组件另有许可 |
| ContourPy | 1.4.0 | BSD-3-Clause；安装发行包LICENSE |
| cycler | 0.12.1 | BSD-3-Clause；安装发行包LICENSE |
| fonttools | 4.68.0 | 主体MIT；[LICENSE.external](https://github.com/fonttools/fonttools/blob/main/LICENSE.external)还列OFL、Apache等组件 |
| kiwisolver | 1.5.1 | BSD-3-Clause；安装发行包LICENSE |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause；安装发行包LICENSE、LICENSE.APACHE、LICENSE.BSD |
| pyparsing | 3.3.3 | MIT；安装发行包LICENSE |
| python-dateutil | 4.0.0 | [较新贡献Apache-2.0、较早部分BSD-3-Clause](https://github.com/dateutil/dateutil/blob/master/LICENSE)；实际LICENSE优先于单一元数据标签 |
| tzdata（Python包） | 2026.6 | Python发行包Apache-2.0，IANA数据另有来源声明；不是Conda tzdata provider的版本号 |

Python/Tk须独立具备。运行Python包闭包是上述11项第三方包；pip、setuptools、wheel是环境工具，不是本项目运行依赖，SciPy也不是本版本运行依赖。

## 原生库、字体与再发行边界

核验的NumPy构建许可中包含OpenBLAS、LAPACK，以及GPL-3.0-or-later WITH GCC-exception-3.1的GCC runtime声明。[该例外](https://gcc.gnu.org/onlinedocs/libstdc%2B%2B/manual/license.html)不是对任意GNU组件的统一MIT授权；DLL文件名含scipy不表示本项目导入SciPy。

Pillow附带许可还包含FreeType的FTL或GPL-2.0-or-later可选条款，以及XZ等组件说明。XZ的核心、GNU派生脚本和构建文件许可范围不同，参见[上游说明](https://tukaani.org/xz/)。不能仅看到GPL文本就把Echo独立源码自动改标GPL，也不能忽略实际附带组件的义务。

Matplotlib发行包内的DejaVu/STIX等字体以及FontTools外部内容各有原版权和许可；使用系统/外部库字体不表示本仓库复制这些字体。本候选没有自己的图片、图标或字体资产。

如果未来另行授权分发库二进制、字体、EXE或环境，应按实际纳入文件重新审查并保留完整许可、NOTICE、适用的修改说明和其他再发行义务。本说明只覆盖当前不捆绑第三方组件的源码方案，不是整个Python环境再发行许可结论。

MIT标准文本参考：[Open Source Initiative](https://opensource.org/license/mit)。滚动上游网页供查阅；精确安装版本的发行包内许可为构建层依据。
