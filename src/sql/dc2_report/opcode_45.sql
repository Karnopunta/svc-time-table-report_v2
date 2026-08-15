--base 45
with base as (
    select
            waybill_no,
           max(oper_time) oper_time
--            extend_attach_4
    from analysis_services.fvp_45
    where oper_dt >= '${STARTDATE}'
      AND oper_dt < '${ENDDATE}'::date+interval '1 day'
      and oper_time>='${STARTDATE}'
      and oper_time<'${ENDDATE}'
     -- and fzone_code='DC1'
      group by 1
) select ba.oper_time::date tanggal,
--          ba.waybill_no,
         coalesce(sc.sc,aws.lh_origin_history) sc_origin,
         TO_CHAR(oper_time, 'HH24') || '.00 - ' || TO_CHAR(oper_time + INTERVAL '1 hour', 'HH24') || '.00'  time_opcode,
         coalesce(scd.sc,aws.lh_destination_history) sc_dest,
         count(*)::text count_awb
         from base ba
    inner join analysis_services.awb_summary aws on aws.awb=ba.waybill_no and aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
             and aws.order_time_dt>='${STARTDATE}'::date-interval '3 month'  and aws.order_time_dt<'${ENDDATE}'::date+interval '1 day'
    left join analysis_services.tm_staging_cluster_uz scd on aws.delivery_unitzone=scd.uz_code
    left join analysis_services.tm_staging_cluster_uz sc on aws.pickup_unitzone=sc.uz_code
    where coalesce(scd.sc,aws.lh_destination_history)>''
    group by 1,2,3,4;