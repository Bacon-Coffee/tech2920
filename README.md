# tech2390 研究项目

基于 SUMO（Eclipse Simulation of Urban MObility）的交通仿真研究项目，配套课程论文与 PPT。

## 环境要求

- macOS（已在 Apple Silicon 上验证）
- Python 3.12（conda env `tech2390`，已验证 traci/sumolib/scipy/pyarrow 等依赖）
- Eclipse SUMO 1.26.0（已通过官方 `.pkg` 安装到 `/Library/Frameworks/EclipseSUMO.framework`）

## 快速开始

1) **确认 SUMO_HOME 已生效**（首次配置完成后请新开终端窗口）：

```bash
echo $SUMO_HOME
# 期望输出：/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/share/sumo

sumo --version
```

2) **激活 conda 环境**（首次创建：`conda create -n tech2390 python=3.12 -y && pip install -r requirements.txt`）：

```bash
conda activate tech2390
cd /Users/xavier-macbookair/Desktop/textbook.Spring/tech2390/project
```

3) **验证 Python TraCI 可用**：

```bash
python -c "import traci, sumolib; print('traci', traci.__version__); print('sumolib OK')"
```

## 目录结构

```
project/
├── sim/             # SUMO 网络 .net.xml、车流 .rou.xml、配置 .sumocfg
├── controllers/     # 5 种信号控制算法（共享 base class）
├── runner/          # 实验编排：参数矩阵、并行调度、结果落盘
├── analysis/        # scipy.stats 统计检验 + matplotlib 出图
├── paper/           # IEEE 论文 .docx + 参考文献
├── results/         # 仿真原始输出（不进 git，见 .gitignore）
├── requirements.txt # Python 依赖
└── README.md
```

当前 `sim/` 已包含：
- `grid4x4.net.xml`（4×4 网格，12 个 actuated 信号灯，2 车道 / 200m / 13.89 m/s）
- `routes_normal_{200,400,600,800,1000}.rou.xml`（5 档名义流量）
- `grid4x4_normal_{200,400,600,800,1000}.sumocfg`（端到端配置，3600s 仿真）

`*.trips.xml` 与 `*.rou.alt.xml` 是 randomTrips/duarouter 的中间产物，已 gitignore（可从 seed 重生）。

## 常用命令

```bash
# 直接跑配置（无 GUI）
sumo -c configs/<name>.sumocfg

# 启动图形界面查看
sumo-gui -c configs/<name>.sumocfg

# 由 OpenStreetMap 生成路网
netconvert --osm-files map.osm -o networks/map.net.xml

# 编辑路网
netedit
```

## Python TraCI 最小示例

```python
import os, sys
import traci

sumo_cmd = ["sumo", "-c", "configs/example.sumocfg"]
traci.start(sumo_cmd)
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
traci.close()
```

## SUMO_HOME 配置说明

已在 `~/.zshrc` 末尾追加：

```bash
export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/share/sumo"
export PATH="/Library/Frameworks/EclipseSUMO.framework/Versions/1.26.0/EclipseSUMO/bin:$PATH"
```

如果 `sumo` 命令找不到，重新打开终端或执行 `source ~/.zshrc`。
