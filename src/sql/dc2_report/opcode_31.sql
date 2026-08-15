with base as (select
                    waybill_no,
--                                coalesce(scd.sc, aws.lh_destination_history) sc_destination,
                    max(oper_time) oper_time
              from analysis_services.fvp_31 f31
              where f31.oper_dt >= '${STARTDATE}'
                AND f31.oper_dt < '${ENDDATE}'
                and f31.oper_time >= '${STARTDATE}'
                and f31.oper_time < '${ENDDATE}'
                AND f31.fzone_code = 'DC2'
    group by 1
--                 and coalesce(scd.sc, aws.lh_destination_history) > ''
--               order by waybill_no, coalesce(scd.sc, aws.lh_destination_history), oper_time desc
) select waybill_no awb,
         coalesce(scd.sc, aws.lh_destination_history) sc_destination,
         oper_time
from base f31
inner join analysis_services.awb_summary aws on aws.awb=f31.waybill_no and aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
             and aws.order_time_dt>='${STARTDATE}'::date-interval '2 month'  and aws.order_time_dt<'${ENDDATE}'
left join analysis_services.tm_staging_cluster_uz scd on aws.delivery_unitzone = scd.uz_code
where 1=1 and coalesce(scd.sc, aws.lh_destination_history) > ''
