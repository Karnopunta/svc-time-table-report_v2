```text
Hasil akhir file:
C:\Repository\svc-time-table-report\data\reports\DAD_REPORT_TIME_TABLE_HUB_20260519.xlsx


Tujuan grouping:
- untuk menghitung jumlah AWB
- count harus berasal dari kolom `awb`
- tambahkan kolom baru:
  `count_awb`

Perbaiki logic grouping menjadi:

GROUP BY:
- date
- hour
- zone_code
- uz_pickup
- uz_delivery
- opcode
- activity

Kemudian:
- hitung jumlah AWB per grouping tersebut
- gunakan:
  COUNT(awb) AS count_awb
  atau pandas equivalent:
  groupby(...).agg(count_awb=('awb','count'))

Expected output:
date | hour | zone_code | uz_pickup | uz_delivery | opcode | activity | count_awb

Pastikan:
- kolom `awb` TIDAK ikut menjadi grouping
- `awb` hanya digunakan untuk counting
- hasil final tidak duplicate per grouping
- output Excel hanya berisi hasil aggregated final

Tolong fokus memperbaiki:
1. grouping logic
2. aggregation count_awb
3. final dataframe output
4. excel export result
```
