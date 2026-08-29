# Blender Fusion Navigation

为习惯 Fusion 360 的用户提供一套轻量、可随时关闭的 Blender 导航和模式菜单过渡层。

插件只修改 Fusion 鼠标导航、3D 视图中的 `Tab` 模式菜单和右上角视图立方体。其它建模和键盘快捷键均保持 Blender 原生行为。

> Blender 5.2 LTS 扩展，界面语言为中文。

## 功能

### Fusion 风格鼠标导航

| 操作 | 功能 |
| --- | --- |
| 鼠标中键拖动 | 平移视图 |
| `Shift + 鼠标中键`拖动 | 旋转视图 |
| 鼠标滚轮 | 缩放视图，保持 Blender 原生行为 |

### Fusion 风格视图立方体

- 替换 Blender 原生导航轴，关闭插件后自动恢复
- 随当前视角实时旋转
- 点击六个面切换前、后、左、右、顶、底视图
- 点击角部切换等轴测视图
- Home 按钮返回默认等轴测视图
- 彩色 `X/Y/Z` 方向标识
- 根据 Blender UI 缩放自动调整尺寸和边距

### Tab 模式菜单

在 3D 视图中按 `Tab` 打开中文模式菜单：

- 对象、顶点、边、面模式
- 撤销
- 恢复视角
- 编辑模式下的遮挡选择
- 切换正交 / 透视

**快速双击 `Tab`**（0.35 秒内按两次）可以直接在物体模式和编辑模式之间切换，无需经过菜单。

插件的键盘快捷键只使用 `Tab`，不会占用 `Q`、Page Down、鼠标侧键或其它 Blender 键盘快捷键。

## 安装

1. 从 [Releases](https://github.com/qwejun/blender-fusion-navigation/releases) 下载最新的 `fusion_keys_navigation-*.zip`。
2. 打开 Blender 5.2 LTS。
3. 进入 `编辑 > 偏好设置 > 获取扩展`。
4. 点击右上角菜单，选择“从磁盘安装”。
5. 选择下载的 ZIP 文件并启用“Fusion 按键与导航”。

不要解压安装包。

## 设置

进入 `编辑 > 偏好设置 > 插件 > Fusion 按键与导航`，可以开关：

- Fusion 鼠标导航
- Fusion 视图立方体
- Tab 模式菜单

关闭或卸载插件后，插件添加的键位会被移除，Blender 原生导航轴也会恢复到启用插件前的状态。

## 从源码构建

在仓库根目录运行：

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  --command extension build `
  --source-dir ".\fusion_keys_navigation" `
  --output-dir ".\dist"
```

校验安装包：

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
  --command extension validate `
  ".\dist\fusion_keys_navigation-0.5.8.zip"
```

## 兼容性

- 已测试：Blender 5.2.0 LTS / Windows
- 最低版本：Blender 5.2.0
- Linux 和 macOS 尚未完成实机测试

## 参与贡献

欢迎提交 Issue 和 Pull Request。提交代码前请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## English

Blender Fusion Navigation is a focused Blender 5.2 LTS add-on that provides Fusion-style mouse navigation, a Chinese Tab mode menu, and an interactive ViewCube.

## 许可与商标

本项目采用 [GNU General Public License v3.0 or later](LICENSE) 发布。

“Fusion 360”和“Autodesk”是其各自权利人的商标。本项目是独立的社区项目，与 Autodesk 无隶属、授权或官方关联。
