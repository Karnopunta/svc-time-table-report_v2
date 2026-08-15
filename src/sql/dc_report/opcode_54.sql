with source as (
select "54_dt"                              tanggal,
       coalesce(scd.sc, aws.lh_destination_history)     sc_destination,
                    analysis_services.f_get_delivery_sla_v5(aws.customer_code, aws.service_code, aws."55_tm",
                                                            aws."80_tm", "80_dt",
                                                            aws.expect_delivery_tm, aws."70_why_code", aws."70_tm",
                                                            aws."81_tm", aws."641_tm",
                                                            aws."54_tm", aws."92_why_code",
                                                            null) AS pickup_sla
                      from analysis_services.awb_summary aws
                      left join analysis_services.tm_staging_cluster_uz scd on aws.delivery_unitzone = scd.uz_code
                      where aws.service_code in ('SDS', 'SD', 'ICE', 'FRS')
                      and aws.order_time_dt >= '${STARTDATE}'::date - interval '2 month' and
                      aws.order_time_dt < '${ENDDATE}'
                      and "54_tm">= '${STARTDATE}' and aws."54_tm" < '${ENDDATE}'
                      and coalesce(scd.sc, aws.lh_destination_history)>''
) select tanggal,
         sc_destination,
         count(*) as count_all,
         count(*) filter ( where pickup_sla='OK') count_ok,
         count(*) filter ( where pickup_sla='Missed') count_missed,
         count(*) filter ( where pickup_sla='Missed by Hour') count_mbh,
         count(*) filter ( where pickup_sla='In Progress' ) count_inprogres
         from source group by 1,2;