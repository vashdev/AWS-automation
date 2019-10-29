''' List All Events  MRPDATA listens to
'''

mrpPrimaEventList=['valuation_pnl','valuation_krd','valuation_pvr', 'valuation_epl']

mrpOtherEventList=['sec_ods', 'loan_sales', 'amtm_loans_cmmt', 'amtm_sec_cmmt', 'amtm_rpl', 'amtm', 'amtm_mf_prices', 'amtm_debts', 'cmh_hot', 'cmh_frontbook', 'front_office', 'ccfa_loan_profile', 'sam_eod', 'sam_eom', 'dgp_inbound_daily', 'dgp_inbound_weekly', 'dgp_inbound_monthly', 'pfe', 'pfecounterparty', 'locus', 'var','portfolio_combiner_guaranty' ]

mrpScheduledEventList=['irdb_prices', 'irdb_rates', 'srdb_volatility','dgp_daily_outbound','DGP_MONTHLY_OUTBOUND_EOD','DGP_MONTHLY_OUTBOUND_EOM']
mrpAmtmEventEntityList=['AMTM_DEBTS_EOD','AMTM_EOD','SUBMIT_LOAN_MARKS_REQ','SUBMIT_MARKS_REQ']

mrpPortfolioSourceEventDict={
                "INFO.LIAB_CRTD_EOD_SNAPSHOT":["FNCL_INSM_EOD_SPST_VW2","liabilities-eod","FANNIE_DAILY"], 
                "INFO.LIAB_CRTD_EOM_SNAPSHOT":["FNCL_INSM_EOM_SPST_VW2" , "liabilities-eom","FANNIE_EOM"],
                "INFO.SF_LNCMT_CRTD_EOD_SNAPSHOT":["CMMT_WHL_LN_ACVY_EOD_SPST_VW2","sf-loan-cmmt-eod","FANNIE_DAILY"],
                "INFO.SF_LNCMT_CRTD_EOM_SNAPSHOT":["CMMT_WHL_LN_EOM_SPST_VW2","sf-loan-cmmt-eom","FANNIE_EOM"],
                "INFO.SF_LN_CRTD_EOD_SNAPSHOT":["LN_AQSN_ACTV_CASH_EOD_SPST_VW2","sf-loans-eod","FANNIE_DAILY"],
                "INFO.SF_LN_CRTD_EOM_SNAPSHOT":["LN_AQSN_ACTV_EOM_SPST_VW2","sf-loans-eom","FANNIE_EOM"],
                "INFO.ASTS_CRTD_EOD_SNAPSHOT":["TRD_PORT_EOD_SPST","asset-securitied-eod","FANNIE_DAILY"],
                "INFO.ASTS_CRTD_EOM_SNAPSHOT":["TRD_PORT_EOM_SPST","asset-securitied-eom","FANNIE_EOM"],
                "INFO.MF_LNCMT_CRTD_EOD_SNAPSHOT":["LN_AQSN_EOD_SPST","mf-loans-eod","FANNIE_DAILY"],
                "INFO.MF_LNAQSN_CRTD_EOM_SNAPSHOT":["LN_AQSN_EOM_SPST","preCombiner-mf-eom-commitments","FANNIE_EOM"],
                "INFO.MF_LNSVCG_CRTD_EOM_SNAPSHOT":["","",""]  , 
                "INFO.LN_AQSN_ACTV_CASH_EOD_SPST":["LN_AQSN_ACTV_CASH_EOD_SPST_VW2","preCombiner-mf-eom-commitments","FANNIE_EOM"]
            }