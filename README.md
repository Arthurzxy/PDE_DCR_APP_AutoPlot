# DCR / PDE / APP Plotter (PyQt5)

一个用于上位机数据对比绘图的小工具：
- 支持按组导入多个 CSV 文件（例如 A/B/C 三组）。
- 支持批量自动分组：按文件名前缀自动归入组，并可附加 `Temp`、`Gate` 参数。
- 从文件名或 CSV 标题行中解析 `DCR`、`PDE`、`APP`。
- 自动生成两张对比图：
  - `PDE vs DCR`（X 轴 PDE%，Y 轴 DCR(k)）
  - `PDE vs APP`（X 轴 PDE%，Y 轴 APP%）
- 上位机可调绘图样式：字体大小、线宽、图尺寸（宽/高，英寸）、图例位置、PDE 数据矫正因子。
- 图例支持自由拖动功能，可在绘图区域实时移动；或通过 `Legend Position` 选项重新定位。
- 支持自定义备注文字，可设置位置并在图内自由拖动。
- 支持 TIFF 导出（DPI 可调，默认 `600`）采用 LZW 压缩格式，文件体积更小。
- 支持复制图片到剪贴板。

## 数据解析规则

标题示例：

`Temp-20-Bias67.5-Gate16-DCR1000-PDE22.38-APP0.53-20260427`

程序会提取：
- `DCR1000` -> 原始值 1000，绘图时换算为 `1.0 k`
- `PDE22.38` -> `22.38 %`
- `APP0.53` -> `0.53 %`

说明：
- 优先从 CSV 内容前几行查找包含 DCR/PDE/APP 的标题。
- 若未找到，则回退到文件名解析。
- 绘图前会按 `PDE` 从小到大排序。

## 批量自动分组规则

- 点击 `Auto Group by Prefix` 可一次导入多文件并自动分组。
- 分组名默认由前缀 + 参数组成，例如：`A-Temp20-Gate16`。
- 前缀取文件名首段（按 `-` 或 `_` 切分）；若首字母是 `A/B/C`，则使用该字母作为组前缀。
- 可通过 `Auto Group Params` 勾选 `Temp`、`Gate` 作为分组参数（至少勾选一个）。
- 若勾选了某参数但文件名缺失该字段（如缺少 `Tempxx`），该文件会提示未分组。

## 快速开始

```powershell
python -m pip install -r requirements.txt
python main.py
```

## 自测

```powershell
python main.py --self-test
```

## 使用步骤

1. 点击 `New Group` 创建组（或重命名为 A/B/C 等）。
2. 选择某个组，点击 `Add CSV Files` 批量导入。
3. 或使用 `Auto Group by Prefix` 批量导入并自动归入 A/B/C 等组。
4. 点击 `Parse + Plot`（添加文件后也会自动重绘）。
5. 在右侧查看两张图（图例在右上角，标签为组名）。
6. 在 `Plot / Export` 中调整绘图样式：
   - `Font Size`、`Line Width`、`Figure Width/Height` 设置图表外观（默认图尺寸为 `8.0 x 5.0 in`）
   - `Legend Position` 调整图例初始位置（支持上左、上右、下左、下右）
   - `PDE Correction Factor` 输入系数，绘图时原始 PDE 值会乘以该系数（默认 `1.0`，范围 `0.01~100`）
   - `Export DPI` 设置导出 TIFF 的分辨率（默认 `600`）
   - 点击 `Apply Style` 预览样式变化
7. 在 `Plot / Export` 中设置 `Note Enabled`、`Note Text`、`Note Position` 和 `Note Font Size`，备注会直接绘制进图片里；图例和备注都支持鼠标拖动。
8. 图例可自由拖动：在图表中鼠标点击并拖动图例，可将其移动到任意位置；或再次调整 `Legend Position` 重新定位图例。
9. 导出：
   - `Save PDE-DCR TIFF`
   - `Save PDE-APP TIFF`
   - `Save Both TIFF`
   可在 `File Suffix` 里设置后缀，文件名如 `PDE-DCR-run1.tiff`。
   所有导出均采用 LZW 无损压缩，文件体积远小于无压缩版本。

