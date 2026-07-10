# convert-units unitUse

Notes `src/lib/convert-units` Use，：

- unit
- unitunit

README  API Notes。

## 1. unit

### 1.1

unit：

```ts
['measure', 'unit']
```

：

```ts
['percent', 'percent']
['percent', 'percent_decimal']
['time', 'ms']
['digital', 'B']
['custom', 'req/s']
```

：

-  1  `measure`：unit
-  2  `unit`：unit

### 1.2

unit：

1. `src/components/ChartSettingStyle/ChartUnitsCascader.vue`
   UI unit， `[measure, unit]`
2. `src/util/Tools.ts`
   `getChartUnitConfig()` unit，unit
3. `src/util/Utils.ts`
   `parseMetricFieldUnit()` unitParse
4. /
   `src/business/Charts/query/QueryChart.vue` Parse `units`

， `convert(1).from().to()`， `[measure, unit]` 。

## 2. unit

Judgment，：

1. ，
   ，， `['custom', 'xxx']`
2. ，
   `82`  `['percent', 'percent']`
   `0.82`  `['percent', 'percent_decimal']`
3. 、、、、Bandwidth，Throughput
   `time` / `timeStamp` / `digital` / `traffic` / `bandWidth` / `throughput`
4. unit
   ，
5. unit UI
   UI ；

## 3. unitunit

Inputsource，。

### 3.1

：

```ts
'percent'
'B'
'ms'
'reqps'
```

 `src/util/Utils.ts`  `metricUnitsMap` ，：

```ts
percent: ['percent', 'percent']
B: ['digital', 'B']
MB: ['digital', 'MB']
ms: ['time', 'ms']
μs: ['time', 'μs']
ns: ['time', 'ns']
reqps: ['throughput', 'reqps']
```

：

```ts
'percent'
```

：

```ts
['percent', 'percent']
```

### 3.2 `measure,unit`

：

```ts
'throughput,reqps'
'percent,percent_decimal'
```

`parseMetricFieldUnit()` ：

```ts
['throughput', 'reqps']
['percent', 'percent_decimal']
```

### 3.3 unit

：

```ts
'custom/["custom","req/s"]'
```

Parse：

```ts
['custom', 'req/s']
```

unit，。

## 4.

`percent` ：

- `src/lib/convert-units/lib/definitions/percent.js`

unit，。

|  |  |  |  |
| --- | --- | --- | --- |
| `['percent', 'percent']` | `0 ~ 100` | `%` | “”， `83.6` |
| `['percent', 'percent_decimal']` | `0.0 ~ 1.0` | `%` | “”， `0.836` |

### 4.1  `%`，

，：

- `percent.to_anchor = 1`
- `percent_decimal.to_anchor = 100`

：

```ts
convert(0.82).from('percent_decimal').to('percent') // 82
convert(82).from('percent').to('percent_decimal')   // 0.82
```

### 4.2 Common errors

- `0.82`  `['percent', 'percent']`， `0.82%`
- `82`  `['percent', 'percent_decimal']`， `8200%`

### 4.3

-  `87.2`、`99.95`、`12.4`， `['percent', 'percent']`
-  `0.872`、`0.9995`、`0.124`， `['percent', 'percent_decimal']`

## 5. unit

### 5.1

`getChartUnitConfig()`  UI：

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

### 5.2  UI

`src/lib/convert-units/lib/index.js`  measure：

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

unit，，unit Cascader 。

## 6.

“ -> unit -> Use cases”。，。

### 6.1 `percent`

、、、SLO 、。

| unit |  |  | Notes |
| --- | --- | --- | --- |
| `percent` | `['percent', 'percent']` | `0 ~ 100` |  |
| `percent_decimal` | `['percent', 'percent_decimal']` | `0 ~ 1` | ， `%` |

：

-  `99.95`
- CPU Use `82.3`
-  `0.998`

### 6.2 `time`

、、、、，“”。

| unit |  | Notes |
| --- | --- | --- |
| `ns` |  span、、 | ， |
| `μs` | tracing、、 |  |
| `ms` | 、、 | ， |
| `s` | 、、 |  |
| `min` | 、、 |  |
| `h` |  |  |
| `d` |  |  |
| `week` |  |  |
| `month` |  |  |
| `year` |  |  |

：

-  `ms`
-  `ns` / `μs` ， `ms`，

### 6.3 `timeStamp`

，“”。

| unit |  | Notes |
| --- | --- | --- |
| `s` | Unix  |  `1710000000` |
| `ms` | JavaScript  |  `1710000000000` |
| `μs` |  | / |
| `ns` |  |  |

：

- `time` “ 200ms”
- `timeStamp` “，”

### 6.4 `digital`

、、、、。

####

| unit | Use cases | Notes |
| --- | --- | --- |
| `b` |  | bit |
| `Kb` | / | kilobit |
| `Mb` |  | megabit |
| `Gb` |  | gigabit |
| `Tb` |  | terabit |
| `Pb` |  | petabit |
| `Eb` |  | exabit |
| `Zb` |  | zettabit |
| `Yb` |  | yottabit |

####

| unit | Use cases | Notes |
| --- | --- | --- |
| `B` | ，、、 | byte |
| `KB` | KB  | kilobyte |
| `MB` | MB  | megabyte |
| `GB` | GB  | gigabyte |
| `TB` | TB  | terabyte |
| `PB` |  | petabyte |
| `EB` |  | exabyte |
| `ZB` |  | zettabyte |
| `YB` |  | yottabyte |

：

- 、、 `B`
- Bandwidth `digital`，Use `bandWidth`
-  `digital`，Use `traffic`

### 6.5 `traffic`

“”，。

| unit | Use cases | Notes |
| --- | --- | --- |
| `B/S` |  |  |
| `KB/S` | KB/s  |  |
| `MB/S` | MB/s  |  |
| `GB/S` | GB/s  |  |
| `TB/S` | Throughput |  |

：

-
-
- /

### 6.6 `bandWidth`

“Bandwidth”。

| unit | Use cases | Notes |
| --- | --- | --- |
| `bps` | Bandwidth | bit/s |
| `Kbps` | Bandwidth | Kbit/s |
| `Mbps` | Bandwidth | Mbit/s |
| `Gbps` | /Bandwidth | Gbit/s |
| `Tbps` | Bandwidth | Tbit/s |

：

- Bandwidth
-
-

`traffic` ：

- `traffic`
- `bandWidth`

### 6.7 `throughput`

Throughput、、action。unit，。

| unit | Use cases | Notes |
| --- | --- | --- |
| `ops` | action | operations per second |
| `reqps` | API/ | requests per second |
| `readps` | action | reads per second，unit `rps` |
| `wps` | action | writes per second |
| `iops` |  IO Throughput | I/O operations per second |
| `opm` | action | operations per minute |
| `readpm` |  | reads per minute，unit `rpm` |
| `wpm` |  | writes per minute |

：

-  QPS
-  IOPS
-

### 6.8 `length`

、、、。

| unit | Use cases | Notes |
| --- | --- | --- |
| `mm` |  | millimeter |
| `cm` |  | centimeter |
| `m` |  | meter |
| `km` |  | kilometer |
| `in` |  | inch |
| `yd` |  | yard |
| `ft-us` |  | US survey foot |
| `ft` |  | foot |
| `mi` |  | mile |

### 6.9 `angle`

、、unit。

| unit | Use cases | Notes |
| --- | --- | --- |
| `rad` | / |  |
| `deg` |  |  |
| `grad` |  | gradian |
| `arcmin` |  | 1/60  |
| `arcsec` |  | 1/3600  |

### 6.10 `mass`

、。

| unit | Use cases | Notes |
| --- | --- | --- |
| `mcg` |  | microgram |
| `mg` |  | milligram |
| `g` |  | gram |
| `kg` |  | kilogram |
| `mt` |  | metric tonne |
| `oz` |  | ounce |
| `lb` |  | pound |
| `t` | / | ton |

### 6.11 `speed`

，“unit”。

| unit | Use cases | Notes |
| --- | --- | --- |
| `m/s` | 、 |  |
| `km/h` |  |  |
| `m/h` |  | mile per hour |
| `knot` | / |  |
| `ft/s` |  | foot per second |

### 6.12 `temperature`

。

| unit | Use cases | Notes |
| --- | --- | --- |
| `C` |  | ， `°C` |
| `K` |  |  |
| `F` |  |  `°F` |
| `R` |  | Rankine |

### 6.13 `frequency`

、、、。

| unit | Use cases | Notes |
| --- | --- | --- |
| `mHz` |  |  |
| `Hz` | unit |  |
| `kHz` |  |  |
| `MHz` |  | CPU/ |
| `GHz` |  |  |
| `THz` |  |  |
| `rpm` |  | revolutions per minute |
| `deg/s` |  |  |
| `rad/s` |  |  |

### 6.14 `rmb`

，unit“//”。

| unit | Use cases | Notes |
| --- | --- | --- |
| `yuan` |  |  |
| `wan_yuan` |  |  |
| `yi_yuan` |  |  |

：

-
-
-

### 6.15 `currencySymbol`

。 `unit` ，Use。

| unit | Use cases | Notes |
| --- | --- | --- |
| `cny` |  |  `¥` |
| `usd` |  |  `$` |
| `eur` |  |  `€` |
| `gbp` |  |  `£` |
| `rub` |  |  `₽` |

：

- unit `unit`  `short_scale`
- ， `prefixUnit`

### 6.16 `number`

， `convert-units` native measure。

| unit | Use cases | Notes |
| --- | --- | --- |
| `default` |  |  |
| `short_scale` |  |  `1.2K / 3.4M / 5.6B`  |

：

- unit，
-

### 6.17 `custom`

、。

|  | Use cases | Notes |
| --- | --- | --- |
| `['custom', 'req/s']` |  |  |
| `['custom', 'FPS']` |  |  |
| `['custom', 'mA']` |  |  |

：

- unit
- unit
- Notes

## 7.  UI unit

unit，，。

### 7.1 `area`

。

| unit | Notes |
| --- | --- |
| `mm2` |  |
| `cm2` |  |
| `m2` |  |
| `ha` |  |
| `km2` |  |
| `in2` |  |
| `yd2` |  |
| `ft2` |  |
| `ac` |  |
| `mi2` |  |

### 7.2 `volume`

。

| unit | Notes |
| --- | --- |
| `mm3` |  |
| `cm3` |  |
| `ml` |  |
| `cl` |  |
| `dl` |  |
| `l` |  |
| `kl` |  |
| `m3` |  |
| `km3` |  |
| `tsp` |  |
| `Tbs` |  |
| `in3` |  |
| `fl-oz` |  |
| `cup` |  |
| `pnt` |  |
| `qt` |  |
| `gal` |  |
| `ft3` |  |
| `yd3` |  |
| `krm` `tsk` `msk` `kkp` `glas` `kanna` | unit |

### 7.3 `volumeFlowRate`

，“unit”。

unit：

| unit | Notes |
| --- | --- |
| `ml/s` |  |
| `l/s` |  |
| `l/min` |  |
| `l/h` |  |
| `m3/s` |  |
| `m3/min` |  |
| `m3/h` |  |
| `gal/s` |  |
| `gal/min` |  |
| `gal/h` |  |
| `ft3/s` |  |
| `ft3/min` |  |
| `ft3/h` |  |

：

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

“”。

| unit | Notes |
| --- | --- |
| `ea` |  |
| `dz` | ， 12  |

### 7.5 `partsPer`

、/。

| unit | Notes |
| --- | --- |
| `ppm` |  |
| `ppb` |  |
| `ppt` |  |
| `ppq` |  |

### 7.6 `pressure`

、。

| unit | Notes |
| --- | --- |
| `Pa` |  |
| `hPa` |  |
| `kPa` |  |
| `MPa` |  |
| `bar` |  |
| `torr` |  |
| `psi` |  |
| `ksi` |  |

### 7.7 `current`

。

| unit | Notes |
| --- | --- |
| `A` |  |
| `mA` |  |
| `kA` |  |

### 7.8 `voltage`

。

| unit | Notes |
| --- | --- |
| `V` |  |
| `mV` |  |
| `kV` |  |

### 7.9 `power`

。

| unit | Notes |
| --- | --- |
| `W` |  |
| `mW` |  |
| `kW` |  |
| `MW` |  |
| `GW` |  |

### 7.10 `reactivePower`

。

| unit | Notes |
| --- | --- |
| `VAR` |  |
| `mVAR` |  |
| `kVAR` |  |
| `MVAR` |  |
| `GVAR` |  |

### 7.11 `apparentPower`

。

| unit | Notes |
| --- | --- |
| `VA` |  |
| `mVA` |  |
| `kVA` |  |
| `MVA` |  |
| `GVA` |  |

### 7.12 `energy`

。

| unit | Notes |
| --- | --- |
| `Wh` |  |
| `mWh` |  |
| `kWh` |  |
| `MWh` |  |
| `GWh` |  |
| `J` |  |
| `kJ` |  |

### 7.13 `reactiveEnergy`

。

| unit | Notes |
| --- | --- |
| `VARh` |  |
| `mVARh` |  |
| `kVARh` |  |
| `MVARh` |  |
| `GVARh` |  |

### 7.14 `illuminance`

。

| unit | Notes |
| --- | --- |
| `lx` |  |
| `ft-cd` |  |

### 7.15 `pace`

“unit”，。

| unit | Notes |
| --- | --- |
| `s/m` |  |
| `min/km` |  |
| `min/mi` |  |
| `s/ft` |  |

### 7.16 `diitalUnit`

，：

- `bandwidthByte`
- `trafficByte`

Use `Tools.ts` ：

- `bandWidth`
- `traffic`

`diitalUnit`，Use `bandWidth` / `traffic`。

## 8.

### 8.1 ，

：

```ts
units: ['percent', 'percent']
units: ['time', 'ms']
units: ['digital', 'B']
units: ['traffic', 'MB/S']
```

：

```ts
unit: 'percent'
unit: 'ms'
unit: 'B'
```

，。

### 8.2 ， `custom`

：

- `req/s`
- `FPS`
- ``
- `/`

unit，：

```ts
['custom', 'req/s']
```

“unit”。

## 9.

|  | unit |
| --- | --- |
| CPU Use `83.2` | `['percent', 'percent']` |
| SLO  `0.9995` | `['percent', 'percent_decimal']` |
|  | `['time', 'ms']` |
| span  | `['time', 'ns']`  `['time', 'μs']` |
|  | `['digital', 'B']` |
|  | `['traffic', 'B/S']` |
| Bandwidth | `['bandWidth', 'Mbps']` |
|  | `['throughput', 'reqps']` |
| IOPS | `['throughput', 'iops']` |
|  | `['rmb', 'yuan']` / `['rmb', 'wan_yuan']` |
|  | `['currencySymbol', 'usd']` |
| unit， `FPS` | `['custom', 'FPS']` |

## 10. unitCheck

-
-
- unit，
- 、， `measure,unit`
- ， `0~100`  `0~1`
- ，`getChartUnitConfig()`
- ， `Utils.metricUnitsMap`

## 11.

-  `0.82`  `82%`， `['percent', 'percent']`
-  `82`  `0.82`， `['percent', 'percent_decimal']`
-  `digital`
- Bandwidth `traffic`
-  `time`
-
-  `definitions/*.js`， UI
- unit，

## 12.

，unit：

1.  `[measure, unit]`
2.  `percent`  `percent_decimal`
3. ， `custom`

，unit。
