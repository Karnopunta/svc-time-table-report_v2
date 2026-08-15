--base 30 SC to dc (ext_4=dc)
with base as (
    select
            waybill_no,
           max(oper_time) oper_time,
           max(extend_attach_4) extend_attach_4
    from analysis_services.fvp_30
    where oper_dt >= '${STARTDATE}'
      AND oper_dt < '${ENDDATE}'::date+interval '1 day'
      and oper_time>='${STARTDATE}'
      and oper_time<'${ENDDATE}'
      and LENGTH(fzone_code)>=4
      and extend_attach_4='DC1'
    group by 1
) select ba.oper_time::date tanggal,
--          ba.waybill_no,
         coalesce(sc.sc,aws.lh_origin_history) sc_origin,
         TO_CHAR(oper_time, 'HH24') || '.00 - ' || TO_CHAR(oper_time + INTERVAL '1 hour', 'HH24') || '.00'  time_opcode,
         coalesce(sc_dest.sc,aws.lh_destination_history) sc_dest,
         count(*)::text count_awb
         from base ba
    inner join analysis_services.awb_summary aws on aws.awb=ba.waybill_no and aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
             and aws.order_time_dt>='${STARTDATE}'::date-interval '3 month'  and aws.order_time_dt<'${ENDDATE}'::date+interval '1 day'
    left join analysis_services.tm_staging_cluster_uz sc on aws.pickup_unitzone=sc.uz_code
    left join analysis_services.tm_staging_cluster_uz sc_dest on aws.delivery_unitzone=sc_dest.uz_code
    group by 1,2,3,4;