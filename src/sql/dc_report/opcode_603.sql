with base as (
    select waybill_no awb,
           max(oper_time) oper_time
    from analysis_services.fvp_603 f603
    where f603.waybill_no in (${AWB_LIST})
      and f603.oper_dt >= '${STARTDATE}'
      AND f603.oper_dt < '${ENDDATE}'
      and f603.oper_time >= '${STARTDATE}'
      and f603.oper_time < '${ENDDATE}'
      AND f603.fzone_code = 'DC1'
    group by 1
) select --distinct on (f603.awb,coalesce(scd.sc,aws.lh_destination_history))
         f603.awb,
         coalesce(scd.sc,aws.lh_destination_history) sc_destination,
         f603.oper_time
         from base f603
inner join analysis_services.awb_summary aws on aws.awb=f603.awb and aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
        and aws.order_time_dt>='${STARTDATE}'::date-interval '2 month'  and aws.order_time_dt<'${ENDDATE}'
    left join analysis_services.tm_staging_cluster_uz scd on aws.delivery_unitzone=scd.uz_code
where coalesce(scd.sc,aws.lh_destination_history)>''
