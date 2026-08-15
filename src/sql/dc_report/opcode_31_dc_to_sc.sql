--base 31 dc_to_sc
with base as (
    select
            waybill_no,
           fzone_code,
           max(oper_time) oper_time,
           max(extend_attach_4) extend_attach_4
    from analysis_services.fvp_31
    where oper_dt >= '${STARTDATE}'
      AND oper_dt < '${ENDDATE}'::date+interval '1 day'
      and oper_time>='${STARTDATE}'
      and oper_time<'${ENDDATE}'
      and fzone_code='DC1'
    group by 1,2
) select ba.oper_time::date tanggal,
--          ba.waybill_no,
         ba.fzone_code sc_origin,
         TO_CHAR(oper_time, 'HH24') || '.00 - ' || TO_CHAR(oper_time + INTERVAL '1 hour', 'HH24') || '.00'  time_opcode,
          coalesce(sc.sc,aws.lh_destination_history) sc_dest,
         count(*)::text count_awb
         from base ba
    inner join analysis_services.awb_summary aws on aws.awb=ba.waybill_no and aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
             and aws.order_time_dt>='${STARTDATE}'::date-interval '3 month'  and aws.order_time_dt<'${ENDDATE}'::date+interval '1 day'
    left join analysis_services.tm_staging_cluster_uz sc on aws.delivery_unitzone=sc.uz_code
    where coalesce(sc.sc,aws.lh_destination_history)>''
group by 1,2,3,4;