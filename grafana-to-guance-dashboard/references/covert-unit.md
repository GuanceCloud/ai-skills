# convert-units 项目单位使用手册

本文档说明本仓库里 `src/lib/convert-units` 的实际使用方式，重点回答两个问题：

- 单位在项目里应该怎么写
- 每个单位分类下的具体单位分别适合什么数据

不再重复上游 README 的通用链式 API 说明。

## 1. 项目里单位到底怎么写

### 1.1 最常见写法

项目内单位的标准写法是二元数组：

```ts
['measure', 'unit']
```

例如：

```ts
['percent', 'percent']
['percent', 'percent_decimal']
['time', 'ms']
['digital', 'B']
['custom', 'req/s']
```

含义：

- 第 1 位 `measure`：单位分类
- 第 2 位 `unit`：该分类下的具体单位

### 1.2 这套配置在仓库里的流转链路

项目里单位配置主要经过下面几层：

1. `src/components/ChartSettingStyle/ChartUnitsCascader.vue`
   负责在图表配置 UI 中选择单位，最终得到 `[measure, unit]`
2. `src/util/Tools.ts`
   `getChartUnitConfig()` 读取库内单位定义，生成图表单位选择器可选项
3. `src/util/Utils.ts`
   `parseMetricFieldUnit()` 把后端或历史字符串单位解析成二元数组
4. 图表/表格渲染链路
   例如 `src/business/Charts/query/QueryChart.vue` 会继续消费解析后的 `units`

所以在本项目里，最重要的不是 `convert(1).from().to()`，而是 `[measure, unit]` 这套统一配置格式。

## 2. 先学会怎么选单位

如果你只想快速判断该填什么，按下面顺序选：

1. 这是一个可换算的数值，还是只是展示后缀
   如果只是加后缀，不做换算，用 `['custom', 'xxx']`
2. 这是百分比的原始值，还是百分比的小数值
   `82` 用 `['percent', 'percent']`
   `0.82` 用 `['percent', 'percent_decimal']`
3. 这是时间长度、时间戳、数据大小、流量、带宽，还是业务吞吐
   按分类选 `time` / `timeStamp` / `digital` / `traffic` / `bandWidth` / `throughput`
4. 这个单位是否已经存在于库定义里
   有现成定义直接复用，没有再考虑扩展
5. 后端返回的是字符串单位还是 UI 显式配置
   UI 配置优先直接写数组；历史字符串再走兼容映射

## 3. 字符串单位和数组单位的关系

项目里同时兼容几种输入来源，最终都会尽量转成二元数组。

### 3.1 直接字符串别名

例如：

```ts
'percent'
'B'
'ms'
'reqps'
```

这类值会通过 `src/util/Utils.ts` 里的 `metricUnitsMap` 做映射，例如：

```ts
percent: ['percent', 'percent']
B: ['digital', 'B']
MB: ['digital', 'MB']
ms: ['time', 'ms']
μs: ['time', 'μs']
ns: ['time', 'ns']
reqps: ['throughput', 'reqps']
```

也就是说：

```ts
'percent'
```

在项目里等价于：

```ts
['percent', 'percent']
```

### 3.2 `measure,unit` 形式字符串

例如：

```ts
'throughput,reqps'
'percent,percent_decimal'
```

`parseMetricFieldUnit()` 会直接拆成：

```ts
['throughput', 'reqps']
['percent', 'percent_decimal']
```

### 3.3 自定义单位字符串

例如：

```ts
'custom/["custom","req/s"]'
```

解析后得到：

```ts
['custom', 'req/s']
```

这类单位不参与库内换算，只负责显示后缀。

## 4. 百分比一定先搞清楚

`percent` 分类定义在：

- `src/lib/convert-units/lib/definitions/percent.js`

它只有两个子单位，但这是项目里最容易配错的一组。

| 配置 | 适用原始值 | 页面最终显示 | 什么时候用 |
| --- | --- | --- | --- |
| `['percent', 'percent']` | `0 ~ 100` | `%` | 后端已经返回“百分数”本身，例如 `83.6` |
| `['percent', 'percent_decimal']` | `0.0 ~ 1.0` | `%` | 后端返回“小数百分比”，例如 `0.836` |

### 4.1 两个都显示 `%`，区别在哪

两者显示符号都一样，差别在换算倍率：

- `percent.to_anchor = 1`
- `percent_decimal.to_anchor = 100`

也就是说：

```ts
convert(0.82).from('percent_decimal').to('percent') // 82
convert(82).from('percent').to('percent_decimal')   // 0.82
```

### 4.2 最常见错误

- `0.82` 配成 `['percent', 'percent']`，页面显示 `0.82%`
- `82` 配成 `['percent', 'percent_decimal']`，页面显示 `8200%`

### 4.3 经验法则

- 原始值看起来像 `87.2`、`99.95`、`12.4`，大概率用 `['percent', 'percent']`
- 原始值看起来像 `0.872`、`0.9995`、`0.124`，大概率用 `['percent', 'percent_decimal']`

## 5. 各单位分类总览

### 5.1 图表选择器里实际会出现的主要分类

`getChartUnitConfig()` 当前会把下面这些分类暴露给 UI：

- `digital`
- `time`
- `timeStamp`
- `traffic`
- `bandWidth`
- `percent`
- `rmb`
- `currencySymbol`
- `frequency`
- `length`
- `angle`
- `mass`
- `number`
- `speed`
- `temperature`
- `throughput`
- `custom`

### 5.2 库里还注册了但当前 UI 不一定常用的分类

`src/lib/convert-units/lib/index.js` 里还注册了这些 measure：

- `area`
- `volume`
- `each`
- `partsPer`
- `pressure`
- `current`
- `voltage`
- `power`
- `reactivePower`
- `apparentPower`
- `energy`
- `reactiveEnergy`
- `volumeFlowRate`
- `illuminance`
- `pace`
- `diitalUnit`

这些单位定义是存在的，可以在代码里直接用，但不一定默认出现在图表单位 Cascader 中。

## 6. 分类详解

下面按“分类 -> 单位 -> 适用场景”来展开。看到这里，基本就可以不查源码直接选。

### 6.1 `percent`

用于成功率、利用率、占比、SLO 达成率、错误率换算后的百分比显示。

| unit | 推荐写法 | 适用数据 | 一句话说明 |
| --- | --- | --- | --- |
| `percent` | `['percent', 'percent']` | `0 ~ 100` | 原始值已经是百分数 |
| `percent_decimal` | `['percent', 'percent_decimal']` | `0 ~ 1` | 原始值是小数比例，展示时转成 `%` |

典型场景：

- 可用性 `99.95`
- CPU 使用率 `82.3`
- 小数成功率 `0.998`

### 6.2 `time`

用于持续时间、耗时、延迟、执行时间、等待时间，不用于“绝对时间点”。

| unit | 推荐场景 | 一句话说明 |
| --- | --- | --- |
| `ns` | 链路 span、内核耗时、探针原始时延 | 纳秒，最细粒度 |
| `μs` | tracing、网络往返耗时、数据库细粒度耗时 | 微秒 |
| `ms` | 接口耗时、前端渲染耗时、常规延迟 | 毫秒，最常用 |
| `s` | 秒级耗时、任务耗时、倒计时 | 秒 |
| `min` | 作业执行时长、巡检周期、聚合耗时 | 分钟 |
| `h` | 小时级时长 | 小时 |
| `d` | 天级持续时间 | 天 |
| `week` | 周级时间跨度 | 周 |
| `month` | 月级时间跨度 | 月 |
| `year` | 年级时间跨度 | 年 |

选型建议：

- 默认先想 `ms`
- 原始数据已经是 `ns` / `μs` 时，不要随便改成 `ms`，除非确定展示层需要自动换算

### 6.3 `timeStamp`

用于时间戳字段，不是“持续时间”。

| unit | 推荐场景 | 说明 |
| --- | --- | --- |
| `s` | Unix 秒级时间戳 | 例如 `1710000000` |
| `ms` | JavaScript 常见时间戳 | 例如 `1710000000000` |
| `μs` | 微秒级时间戳 | 常见于链路/观测原始数据 |
| `ns` | 纳秒级时间戳 | 高精度采集数据 |

区别：

- `time` 是“耗时 200ms”
- `timeStamp` 是“发生在某个时间点，值本身是时间戳”

### 6.4 `digital`

用于数据大小、内存、磁盘、对象体积、字节数。

#### 比特系

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `b` | 原始比特数 | bit |
| `Kb` | 小规模网络/传输比特量 | kilobit |
| `Mb` | 中等比特量 | megabit |
| `Gb` | 大规模比特量 | gigabit |
| `Tb` | 超大比特量 | terabit |
| `Pb` | 极大比特量 | petabit |
| `Eb` | 极大比特量 | exabit |
| `Zb` | 极大比特量 | zettabit |
| `Yb` | 极大比特量 | yottabit |

#### 字节系

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `B` | 最常用，文件大小、内存、流量字节数 | byte |
| `KB` | KB 级体积 | kilobyte |
| `MB` | MB 级体积 | megabyte |
| `GB` | GB 级体积 | gigabyte |
| `TB` | TB 级体积 | terabyte |
| `PB` | 超大存储量 | petabyte |
| `EB` | 超大存储量 | exabyte |
| `ZB` | 超大存储量 | zettabyte |
| `YB` | 超大存储量 | yottabyte |

选型建议：

- 存储、内存、磁盘空间默认优先 `B`
- 带宽不要用 `digital`，应使用 `bandWidth`
- 每秒字节流量不要用 `digital`，应使用 `traffic`

### 6.5 `traffic`

用于“每秒字节流量”，本质上是项目额外定义的展示分类。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `B/S` | 最常用 | 每秒字节 |
| `KB/S` | KB/s 流量 | 每秒千字节 |
| `MB/S` | MB/s 流量 | 每秒兆字节 |
| `GB/S` | GB/s 流量 | 每秒吉字节 |
| `TB/S` | 超大吞吐 | 每秒太字节 |

适合：

- 网卡收发速率
- 磁盘读写速率
- 下载/上传字节速率

### 6.6 `bandWidth`

用于“每秒比特带宽”。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `bps` | 原始比特带宽 | bit/s |
| `Kbps` | 千比特带宽 | Kbit/s |
| `Mbps` | 最常见网络带宽 | Mbit/s |
| `Gbps` | 机房/网络大带宽 | Gbit/s |
| `Tbps` | 超大带宽 | Tbit/s |

适合：

- 网络带宽
- 线路速率
- 接口协商速率

不要和 `traffic` 混用：

- `traffic` 是字节每秒
- `bandWidth` 是比特每秒

### 6.7 `throughput`

用于业务吞吐量、请求率、操作率。这个分类在库里基本只负责加单位名，不做数值换算。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `ops` | 泛化操作次数 | operations per second |
| `reqps` | API/服务请求率 | requests per second |
| `readps` | 读操作速率 | reads per second，展示单位为 `rps` |
| `wps` | 写操作速率 | writes per second |
| `iops` | 磁盘 IO 吞吐 | I/O operations per second |
| `opm` | 分钟级操作量 | operations per minute |
| `readpm` | 分钟级读速率 | reads per minute，展示单位为 `rpm` |
| `wpm` | 分钟级写速率 | writes per minute |

适合：

- 服务 QPS
- 磁盘 IOPS
- 数据库读写速率

### 6.8 `length`

用于长度、距离、位移、尺寸。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `mm` | 毫米级尺寸 | millimeter |
| `cm` | 厘米级尺寸 | centimeter |
| `m` | 米级长度 | meter |
| `km` | 千米级距离 | kilometer |
| `in` | 英寸 | inch |
| `yd` | 码 | yard |
| `ft-us` | 美制测量英尺 | US survey foot |
| `ft` | 国际通用英尺 | foot |
| `mi` | 英里 | mile |

### 6.9 `angle`

用于角度、方向偏移、旋转速度的单位基础值。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `rad` | 数学/物理原始角度 | 弧度 |
| `deg` | 最常见角度显示 | 度 |
| `grad` | 梯度制 | gradian |
| `arcmin` | 角分 | 1/60 度 |
| `arcsec` | 角秒 | 1/3600 度 |

### 6.10 `mass`

用于质量、重量。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `mcg` | 微克级数据 | microgram |
| `mg` | 毫克级数据 | milligram |
| `g` | 克级数据 | gram |
| `kg` | 千克级数据 | kilogram |
| `mt` | 公吨 | metric tonne |
| `oz` | 盎司 | ounce |
| `lb` | 磅 | pound |
| `t` | 英吨/吨 | ton |

### 6.11 `speed`

用于速度，而不是“每单位距离耗时”。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `m/s` | 科学计算、设备速度 | 米每秒 |
| `km/h` | 常见速度显示 | 千米每时 |
| `m/h` | 英里每小时 | mile per hour |
| `knot` | 航海/航空速度 | 节 |
| `ft/s` | 英尺每秒 | foot per second |

### 6.12 `temperature`

用于温度。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `C` | 最常用 | 摄氏度，显示 `°C` |
| `K` | 绝对温标 | 开尔文 |
| `F` | 华氏温标 | 显示 `°F` |
| `R` | 兰金温标 | Rankine |

### 6.13 `frequency`

用于频率、采样率、转速、角速度。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `mHz` | 低频变化 | 毫赫兹 |
| `Hz` | 最常用频率单位 | 赫兹 |
| `kHz` | 千赫兹 | 高频采样 |
| `MHz` | 兆赫兹 | CPU/信号 |
| `GHz` | 吉赫兹 | 高频时钟 |
| `THz` | 太赫兹 | 极高频 |
| `rpm` | 转速 | revolutions per minute |
| `deg/s` | 角速度 | 度每秒 |
| `rad/s` | 角速度 | 弧度每秒 |

### 6.14 `rmb`

用于人民币数值，单位是“元/万/亿”。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `yuan` | 普通金额 | 元 |
| `wan_yuan` | 万级金额 | 万 |
| `yi_yuan` | 亿级金额 | 亿 |

适合：

- 成本金额
- 账单金额
- 消费金额

### 6.15 `currencySymbol`

用于带货币前缀的金额显示。这个分类的 `unit` 不是普通后缀，而是会配合前缀符号使用。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `cny` | 人民币金额 | 前缀 `¥` |
| `usd` | 美元金额 | 前缀 `$` |
| `eur` | 欧元金额 | 前缀 `€` |
| `gbp` | 英镑金额 | 前缀 `£` |
| `rub` | 卢布金额 | 前缀 `₽` |

注意：

- 这类单位定义里 `unit` 是 `short_scale`
- 重点不是后缀，而是 `prefixUnit`

### 6.16 `number`

这是项目额外补的普通数字展示分类，不是 `convert-units` 原生 measure。

| unit | 适用场景 | 说明 |
| --- | --- | --- |
| `default` | 原样显示数字 | 不做缩写 |
| `short_scale` | 大数缩写 | 常见于 `1.2K / 3.4M / 5.6B` 这类展示 |

适合：

- 没有业务单位，但数值很大
- 希望统一做大数缩写

### 6.17 `custom`

用于仅展示后缀、不做换算的场景。

| 写法 | 适用场景 | 说明 |
| --- | --- | --- |
| `['custom', 'req/s']` | 自定义请求率后缀 | 只展示 |
| `['custom', 'FPS']` | 帧率 | 只展示 |
| `['custom', 'mA']` | 某些业务自定义电流展示 | 只展示 |

什么时候用：

- 库里没有这个单位
- 不需要跨单位换算
- 只是想给数字加一个说明性后缀

## 7. 库里已定义但当前不一定常在 UI 里直接选到的单位

如果你是在代码里手写单位，而不是只依赖图表设置面板，下面这些分类也可以直接用。

### 7.1 `area`

用于面积。

| unit | 说明 |
| --- | --- |
| `mm2` | 平方毫米 |
| `cm2` | 平方厘米 |
| `m2` | 平方米 |
| `ha` | 公顷 |
| `km2` | 平方千米 |
| `in2` | 平方英寸 |
| `yd2` | 平方码 |
| `ft2` | 平方英尺 |
| `ac` | 英亩 |
| `mi2` | 平方英里 |

### 7.2 `volume`

用于体积和容量。

| unit | 说明 |
| --- | --- |
| `mm3` | 立方毫米 |
| `cm3` | 立方厘米 |
| `ml` | 毫升 |
| `cl` | 厘升 |
| `dl` | 分升 |
| `l` | 升 |
| `kl` | 千升 |
| `m3` | 立方米 |
| `km3` | 立方千米 |
| `tsp` | 茶匙 |
| `Tbs` | 汤匙 |
| `in3` | 立方英寸 |
| `fl-oz` | 液量盎司 |
| `cup` | 杯 |
| `pnt` | 品脱 |
| `qt` | 夸脱 |
| `gal` | 加仑 |
| `ft3` | 立方英尺 |
| `yd3` | 立方码 |
| `krm` `tsk` `msk` `kkp` `glas` `kanna` | 瑞典制容量单位 |

### 7.3 `volumeFlowRate`

用于体积流量，也就是“单位时间内流过多少体积”。

常用单位：

| unit | 说明 |
| --- | --- |
| `ml/s` | 毫升每秒 |
| `l/s` | 升每秒 |
| `l/min` | 升每分钟 |
| `l/h` | 升每小时 |
| `m3/s` | 立方米每秒 |
| `m3/min` | 立方米每分钟 |
| `m3/h` | 立方米每小时 |
| `gal/s` | 加仑每秒 |
| `gal/min` | 加仑每分钟 |
| `gal/h` | 加仑每小时 |
| `ft3/s` | 立方英尺每秒 |
| `ft3/min` | 立方英尺每分钟 |
| `ft3/h` | 立方英尺每小时 |

此外还支持：

- `mm3/s`
- `cm3/s`
- `cl/s`
- `dl/s`
- `kl/s`
- `kl/min`
- `kl/h`
- `km3/s`
- `tsp/s`
- `Tbs/s`
- `in3/s`
- `in3/min`
- `in3/h`
- `fl-oz/s`
- `fl-oz/min`
- `fl-oz/h`
- `cup/s`
- `pnt/s`
- `pnt/min`
- `pnt/h`
- `qt/s`
- `yd3/s`
- `yd3/min`
- `yd3/h`

### 7.4 `each`

用于“个数”。

| unit | 说明 |
| --- | --- |
| `ea` | 单个 |
| `dz` | 打，一打等于 12 个 |

### 7.5 `partsPer`

用于百万分比、十亿分比这类浓度/占比描述。

| unit | 说明 |
| --- | --- |
| `ppm` | 百万分之一 |
| `ppb` | 十亿分之一 |
| `ppt` | 万亿分之一 |
| `ppq` | 千万亿分之一 |

### 7.6 `pressure`

用于压强、压力。

| unit | 说明 |
| --- | --- |
| `Pa` | 帕斯卡 |
| `hPa` | 百帕 |
| `kPa` | 千帕 |
| `MPa` | 兆帕 |
| `bar` | 巴 |
| `torr` | 托 |
| `psi` | 磅力每平方英寸 |
| `ksi` | 千磅力每平方英寸 |

### 7.7 `current`

用于电流。

| unit | 说明 |
| --- | --- |
| `A` | 安培 |
| `mA` | 毫安 |
| `kA` | 千安 |

### 7.8 `voltage`

用于电压。

| unit | 说明 |
| --- | --- |
| `V` | 伏特 |
| `mV` | 毫伏 |
| `kV` | 千伏 |

### 7.9 `power`

用于有功功率。

| unit | 说明 |
| --- | --- |
| `W` | 瓦 |
| `mW` | 毫瓦 |
| `kW` | 千瓦 |
| `MW` | 兆瓦 |
| `GW` | 吉瓦 |

### 7.10 `reactivePower`

用于无功功率。

| unit | 说明 |
| --- | --- |
| `VAR` | 乏 |
| `mVAR` | 毫乏 |
| `kVAR` | 千乏 |
| `MVAR` | 兆乏 |
| `GVAR` | 吉乏 |

### 7.11 `apparentPower`

用于视在功率。

| unit | 说明 |
| --- | --- |
| `VA` | 伏安 |
| `mVA` | 毫伏安 |
| `kVA` | 千伏安 |
| `MVA` | 兆伏安 |
| `GVA` | 吉伏安 |

### 7.12 `energy`

用于能量。

| unit | 说明 |
| --- | --- |
| `Wh` | 瓦时 |
| `mWh` | 毫瓦时 |
| `kWh` | 千瓦时 |
| `MWh` | 兆瓦时 |
| `GWh` | 吉瓦时 |
| `J` | 焦耳 |
| `kJ` | 千焦 |

### 7.13 `reactiveEnergy`

用于无功能量。

| unit | 说明 |
| --- | --- |
| `VARh` | 乏时 |
| `mVARh` | 毫乏时 |
| `kVARh` | 千乏时 |
| `MVARh` | 兆乏时 |
| `GVARh` | 吉乏时 |

### 7.14 `illuminance`

用于照度。

| unit | 说明 |
| --- | --- |
| `lx` | 勒克斯 |
| `ft-cd` | 英尺烛光 |

### 7.15 `pace`

用于“每单位距离耗时”，常见于跑步配速。

| unit | 说明 |
| --- | --- |
| `s/m` | 秒每米 |
| `min/km` | 分每公里 |
| `min/mi` | 分每英里 |
| `s/ft` | 秒每英尺 |

### 7.16 `diitalUnit`

这是库里注册的历史拼写项，定义的是项目补充的：

- `bandwidthByte`
- `trafficByte`

但当前图表选择器实际使用的是项目在 `Tools.ts` 里补的：

- `bandWidth`
- `traffic`

所以业务代码里一般不用直接依赖 `diitalUnit`，优先使用项目现有的 `bandWidth` / `traffic`。

## 8. 项目里最推荐的写法

### 8.1 能直接写数组，就不要只写字符串

推荐：

```ts
units: ['percent', 'percent']
units: ['time', 'ms']
units: ['digital', 'B']
units: ['traffic', 'MB/S']
```

不推荐只靠字符串别名表达业务含义：

```ts
unit: 'percent'
unit: 'ms'
unit: 'B'
```

因为数组写法更直接，也更不容易在兼容链路里出现歧义。

### 8.2 没有换算诉求时，优先 `custom`

如果只是想显示：

- `req/s`
- `FPS`
- `件`
- `个/分`

这种只做展示的单位，直接用：

```ts
['custom', 'req/s']
```

不要为了“长得像单位”就硬塞进某个可换算分类。

## 9. 常见场景速查

| 场景 | 推荐单位 |
| --- | --- |
| CPU 使用率原始值是 `83.2` | `['percent', 'percent']` |
| SLO 成功率原始值是 `0.9995` | `['percent', 'percent_decimal']` |
| 接口耗时 | `['time', 'ms']` |
| span 原始耗时 | `['time', 'ns']` 或 `['time', 'μs']` |
| 文件大小 | `['digital', 'B']` |
| 网卡字节流量 | `['traffic', 'B/S']` |
| 网络带宽 | `['bandWidth', 'Mbps']` |
| 请求率 | `['throughput', 'reqps']` |
| IOPS | `['throughput', 'iops']` |
| 人民币金额 | `['rmb', 'yuan']` / `['rmb', 'wan_yuan']` |
| 美元金额 | `['currencySymbol', 'usd']` |
| 没有标准单位，只想显示 `FPS` | `['custom', 'FPS']` |

## 10. 新增单位前的检查清单

- 这个值真的需要换算吗
- 它属于现有哪个分类
- 原始值是基础单位值，还是已经换算过的展示值
- 后端传来的是数组、别名字符串，还是 `measure,unit` 字符串
- 如果是百分比，原始值到底是 `0~100` 还是 `0~1`
- 如果要在图表设置里可选，`getChartUnitConfig()` 是否已能列出
- 如果是历史字符串兼容，是否需要补 `Utils.metricUnitsMap`

## 11. 最容易踩坑的点

- 把 `0.82` 当成 `82%`，结果错用 `['percent', 'percent']`
- 把 `82` 当成 `0.82`，结果错用 `['percent', 'percent_decimal']`
- 把字节流量写成 `digital`
- 把比特带宽写成 `traffic`
- 把时间戳字段写成 `time`
- 把只做展示的自定义后缀误放进可换算分类
- 只改了 `definitions/*.js`，但没确认 UI 是否能选到
- 只传字符串单位，却没补兼容映射

## 12. 结论

对这个项目来说，选单位时优先记住下面三条：

1. 先决定是不是 `[measure, unit]`
2. 百分比先分清 `percent` 和 `percent_decimal`
3. 不需要换算时，直接用 `custom`

只要这三条没错，绝大多数单位问题都不会配偏。
