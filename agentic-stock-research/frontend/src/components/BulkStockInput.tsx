import { useState } from 'react'
import { Icons } from './icons'

interface BulkStockInputProps {
  onAnalyze: (tickers: string[], mode: 'buy' | 'sell') => void
  loading?: boolean
}

export function BulkStockInput({ onAnalyze, loading }: BulkStockInputProps) {
  const [inputText, setInputText] = useState('')
  const [mode, setMode] = useState<'buy' | 'sell'>('buy')
  const [error, setError] = useState('')

  // Comprehensive watchlists organized by categories
  const presetLists = {
    // NIFTY Indices
    'NIFTY 50': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS', 'BHARTIARTL.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS', 'TATAMOTORS.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'GRASIM.NS', 'EICHERMOT.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'SUNPHARMA.NS', 'APOLLOHOSP.NS', 'INDUSINDBK.NS', 'AXISBANK.NS', 'ICICIBANK.NS', 'HDFCLIFE.NS', 'SBILIFE.NS', 'BAJAJHLDNG.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS', 'BPCL.NS', 'IOC.NS', 'HINDALCO.NS'],
    
    'NIFTY Next 50': ['ADANIGREEN.NS', 'ADANITRANS.NS', 'BAJAJ-AUTO.NS', 'BERGEPAINT.NS', 'BIOCON.NS', 'CADILAHC.NS', 'CHOLAFIN.NS', 'COLPAL.NS', 'CONCOR.NS', 'DABUR.NS', 'DMART.NS', 'GAIL.NS', 'GODREJCP.NS', 'HDFCAMC.NS', 'HINDCOPPER.NS', 'IDEA.NS', 'IGL.NS', 'INDIGO.NS', 'JINDALSTEL.NS', 'LICHSGFIN.NS', 'LUPIN.NS', 'MCDOWELL-N.NS', 'MFSL.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'PAGEIND.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS'],
    
    'NIFTY 100': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS', 'TATAMOTORS.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'GRASIM.NS', 'EICHERMOT.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'SUNPHARMA.NS', 'APOLLOHOSP.NS', 'INDUSINDBK.NS', 'AXISBANK.NS', 'ICICIBANK.NS', 'HDFCLIFE.NS', 'SBILIFE.NS', 'BAJAJHLDNG.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS', 'BPCL.NS', 'IOC.NS', 'HINDALCO.NS', 'ADANIGREEN.NS', 'ADANITRANS.NS', 'BAJAJ-AUTO.NS', 'BERGEPAINT.NS', 'BIOCON.NS', 'CADILAHC.NS', 'CHOLAFIN.NS', 'COLPAL.NS', 'CONCOR.NS', 'DABUR.NS', 'DMART.NS', 'GAIL.NS', 'GODREJCP.NS', 'HDFCAMC.NS', 'HINDCOPPER.NS', 'IDEA.NS', 'IGL.NS', 'INDIGO.NS', 'JINDALSTEL.NS', 'LICHSGFIN.NS', 'LUPIN.NS', 'MCDOWELL-N.NS', 'MFSL.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'PAGEIND.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS'],
    
    'NIFTY 200': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS', 'TATAMOTORS.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'GRASIM.NS', 'EICHERMOT.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'SUNPHARMA.NS', 'APOLLOHOSP.NS', 'INDUSINDBK.NS', 'AXISBANK.NS', 'ICICIBANK.NS', 'HDFCLIFE.NS', 'SBILIFE.NS', 'BAJAJHLDNG.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS', 'BPCL.NS', 'IOC.NS', 'HINDALCO.NS', 'ADANIGREEN.NS', 'ADANITRANS.NS', 'BAJAJ-AUTO.NS', 'BERGEPAINT.NS', 'BIOCON.NS', 'CADILAHC.NS', 'CHOLAFIN.NS', 'COLPAL.NS', 'CONCOR.NS', 'DABUR.NS', 'DMART.NS', 'GAIL.NS', 'GODREJCP.NS', 'HDFCAMC.NS', 'HINDCOPPER.NS', 'IDEA.NS', 'IGL.NS', 'INDIGO.NS', 'JINDALSTEL.NS', 'LICHSGFIN.NS', 'LUPIN.NS', 'MCDOWELL-N.NS', 'MFSL.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'PAGEIND.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS', 'ABBOTINDIA.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPOWER.NS', 'ALKEM.NS', 'AMBUJACEM.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASTRAL.NS', 'ATUL.NS', 'AUBANK.NS', 'BANDHANBNK.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS', 'BERGERPAINT.NS', 'BHEL.NS', 'BOSCHLTD.NS', 'CROMPTON.NS', 'CUMMINSIND.NS', 'DEEPAKNTR.NS', 'DLF.NS', 'ESCORTS.NS', 'EXIDEIND.NS', 'FEDERALBNK.NS', 'FORTIS.NS', 'GLENMARK.NS', 'GODREJIND.NS', 'GODREJPROP.NS', 'HAVELLS.NS', 'HDFCAMC.NS', 'HINDPETRO.NS', 'HINDZINC.NS', 'IBULHSGFIN.NS', 'ICICIGI.NS', 'ICICIPRULI.NS', 'IDFCFIRSTB.NS', 'INDIAMART.NS', 'INDIGO.NS', 'INFIBEAM.NS', 'IRCTC.NS', 'JKCEMENT.NS', 'JUBLFOOD.NS', 'JUSTDIAL.NS', 'KANSAINER.NS', 'LALPATHLAB.NS', 'LARSEN.NS', 'LATENTVIEW.NS', 'LUXIND.NS', 'MANAPPURAM.NS', 'MARICO.NS', 'MCDOWELL-N.NS', 'METROPOLIS.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'NMDC.NS', 'OBEROI.NS', 'OFSS.NS', 'PAGEIND.NS', 'PEL.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS'],
    
    // Sectoral Indices
    'Bank Nifty': ['HDFCBANK.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'INDUSINDBK.NS', 'BANDHANBNK.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS', 'RBLBANK.NS', 'YESBANK.NS', 'AUBANK.NS'],
    
    'NIFTY IT': ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'LTI.NS', 'MINDTREE.NS', 'MPHASIS.NS', 'OFSS.NS', 'LATENTVIEW.NS'],
    
    'NIFTY Pharma': ['SUNPHARMA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'AUROPHAR MO.NS', 'LUPIN.NS', 'BIOCON.NS', 'CADILAHC.NS', 'TORNTPHARM.NS', 'GLENMARK.NS', 'ALKEM.NS', 'ABBOTINDIA.NS'],
    
    'NIFTY Auto': ['MARUTI.NS', 'TATAMOTORS.NS', 'BAJAJ-AUTO.NS', 'HEROMOTOCO.NS', 'EICHERMOT.NS', 'MOTHERSON.NS', 'ASHOKLEY.NS', 'ESCORTS.NS', 'BOSCHLTD.NS', 'EXIDEIND.NS', 'APOLLOTYRE.NS', 'CUMMINSIND.NS'],
    
    'NIFTY FMCG': ['HINDUNILVR.NS', 'ITC.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DABUR.NS', 'GODREJCP.NS', 'COLPAL.NS', 'MARICO.NS', 'JUBLFOOD.NS', 'TATACONSUM.NS', 'UBL.NS', 'MCDOWELL-N.NS'],
    
    'NIFTY Metal': ['TATASTEEL.NS', 'JSWSTEEL.NS', 'HINDALCO.NS', 'VEDL.NS', 'SAIL.NS', 'JINDALSTEL.NS', 'HINDCOPPER.NS', 'NMDC.NS', 'HINDZINC.NS', 'COALINDIA.NS'],
    
    'NIFTY Energy': ['RELIANCE.NS', 'ONGC.NS', 'COALINDIA.NS', 'BPCL.NS', 'IOC.NS', 'HINDPETRO.NS', 'GAIL.NS', 'PETRONET.NS', 'ADANIGREEN.NS', 'ADANIPOWER.NS', 'ADANITRANS.NS', 'ADANIENT.NS'],
    
    'NIFTY Realty': ['DLF.NS', 'GODREJPROP.NS', 'OBEROI.NS', 'BRIGADE.NS', 'SUNTEKREALTY.NS', 'MAHLIFE.NS', 'SOBHA.NS', 'PURAVANKARA.NS', 'GODREJPROP.NS', 'MAHINDALIFE.NS'],
    
    'NIFTY Media': ['ZEEL.NS', 'SUNTV.NS', 'NETWORK18.NS', 'TVTODAY.NS', 'JAGRAN.NS', 'HTMEDIA.NS', 'DEN.NS', 'TV18BRDCST.NS', 'BALAJITELE.NS', 'INOXLEISUR.NS'],
    
    'NIFTY PSU Bank': ['SBIN.NS', 'PNB.NS', 'BANKBARODA.NS', 'CANFINHOME.NS', 'UNIONBANK.NS', 'CENTRALBK.NS', 'INDIANB.NS', 'BANKINDIA.NS', 'UCOBANK.NS', 'IOB.NS'],
    
    'NIFTY Private Bank': ['HDFCBANK.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'AXISBANK.NS', 'INDUSINDBK.NS', 'BANDHANBNK.NS', 'FEDERALBNK.NS', 'IDFCFIRSTB.NS', 'RBLBANK.NS', 'YESBANK.NS'],
    
    // Market Cap Categories
    'Large Cap': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'POWERGRID.NS', 'NTPC.NS', 'ONGC.NS', 'COALINDIA.NS', 'TATAMOTORS.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'GRASIM.NS', 'EICHERMOT.NS', 'BAJAJFINSV.NS', 'HEROMOTOCO.NS', 'BRITANNIA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'SUNPHARMA.NS', 'APOLLOHOSP.NS', 'INDUSINDBK.NS', 'AXISBANK.NS', 'ICICIBANK.NS', 'HDFCLIFE.NS', 'SBILIFE.NS', 'BAJAJHLDNG.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS', 'BPCL.NS', 'IOC.NS', 'HINDALCO.NS'],
    
    'Mid Cap': ['ADANIGREEN.NS', 'ADANITRANS.NS', 'BAJAJ-AUTO.NS', 'BERGEPAINT.NS', 'BIOCON.NS', 'CADILAHC.NS', 'CHOLAFIN.NS', 'COLPAL.NS', 'CONCOR.NS', 'DABUR.NS', 'DMART.NS', 'GAIL.NS', 'GODREJCP.NS', 'HDFCAMC.NS', 'HINDCOPPER.NS', 'IDEA.NS', 'IGL.NS', 'INDIGO.NS', 'JINDALSTEL.NS', 'LICHSGFIN.NS', 'LUPIN.NS', 'MCDOWELL-N.NS', 'MFSL.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'PAGEIND.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS'],
    
    'Small Cap': ['ABBOTINDIA.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPOWER.NS', 'ALKEM.NS', 'AMBUJACEM.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASTRAL.NS', 'ATUL.NS', 'AUBANK.NS', 'BANDHANBNK.NS', 'BATAINDIA.NS', 'BEL.NS', 'BEML.NS', 'BERGERPAINT.NS', 'BHEL.NS', 'BOSCHLTD.NS', 'CROMPTON.NS', 'CUMMINSIND.NS', 'DEEPAKNTR.NS', 'DLF.NS', 'ESCORTS.NS', 'EXIDEIND.NS', 'FEDERALBNK.NS', 'FORTIS.NS', 'GLENMARK.NS', 'GODREJIND.NS', 'GODREJPROP.NS', 'HAVELLS.NS', 'HDFCAMC.NS', 'HINDPETRO.NS', 'HINDZINC.NS', 'IBULHSGFIN.NS', 'ICICIGI.NS', 'ICICIPRULI.NS', 'IDFCFIRSTB.NS', 'INDIAMART.NS', 'INDIGO.NS', 'INFIBEAM.NS', 'IRCTC.NS', 'JKCEMENT.NS', 'JUBLFOOD.NS', 'JUSTDIAL.NS', 'KANSAINER.NS', 'LALPATHLAB.NS', 'LARSEN.NS', 'LATENTVIEW.NS', 'LUXIND.NS', 'MANAPPURAM.NS', 'MARICO.NS', 'MCDOWELL-N.NS', 'METROPOLIS.NS', 'MINDTREE.NS', 'MOTHERSON.NS', 'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NAUKRI.NS', 'NMDC.NS', 'OBEROI.NS', 'OFSS.NS', 'PAGEIND.NS', 'PEL.NS', 'PETRONET.NS', 'PIDILITIND.NS', 'PNB.NS', 'POLYCAB.NS', 'PVR.NS', 'RBLBANK.NS', 'SAIL.NS', 'SIEMENS.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'VEDL.NS', 'VOLTAS.NS', 'WHIRLPOOL.NS', 'YESBANK.NS', 'ZEEL.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBZR.NS', 'DELTACORP.NS', 'GODREJPROP.NS'],
    
    // BSE Indices
    'BSE Sensex': ['RELIANCE.BO', 'TCS.BO', 'HDFCBANK.BO', 'INFY.BO', 'HINDUNILVR.BO', 'ITC.BO', 'SBIN.BO', 'BHARTIARTL.BO', 'KOTAKBANK.BO', 'LT.BO', 'ASIANPAINT.BO', 'MARUTI.BO', 'NESTLEIND.BO', 'ULTRACEMCO.BO', 'TITAN.BO', 'POWERGRID.BO', 'NTPC.BO', 'ONGC.BO', 'COALINDIA.BO', 'TATAMOTORS.BO', 'BAJFINANCE.BO', 'WIPRO.BO', 'HCLTECH.BO', 'TECHM.BO', 'ADANIPORTS.BO', 'JSWSTEEL.BO', 'TATASTEEL.BO', 'GRASIM.BO', 'EICHERMOT.BO', 'BAJAJFINSV.BO', 'HEROMOTOCO.BO'],
    
    'BSE 100': ['RELIANCE.BO', 'TCS.BO', 'HDFCBANK.BO', 'INFY.BO', 'HINDUNILVR.BO', 'ITC.BO', 'SBIN.BO', 'BHARTIARTL.BO', 'KOTAKBANK.BO', 'LT.BO', 'ASIANPAINT.BO', 'MARUTI.BO', 'NESTLEIND.BO', 'ULTRACEMCO.BO', 'TITAN.BO', 'POWERGRID.BO', 'NTPC.BO', 'ONGC.BO', 'COALINDIA.BO', 'TATAMOTORS.BO', 'BAJFINANCE.BO', 'WIPRO.BO', 'HCLTECH.BO', 'TECHM.BO', 'ADANIPORTS.BO', 'JSWSTEEL.BO', 'TATASTEEL.BO', 'GRASIM.BO', 'EICHERMOT.BO', 'BAJAJFINSV.BO', 'HEROMOTOCO.BO', 'BRITANNIA.BO', 'DIVISLAB.BO', 'DRREDDY.BO', 'CIPLA.BO', 'SUNPHARMA.BO', 'APOLLOHOSP.BO', 'INDUSINDBK.BO', 'AXISBANK.BO', 'ICICIBANK.BO', 'HDFCLIFE.BO', 'SBILIFE.BO', 'BAJAJHLDNG.BO', 'TATACONSUM.BO', 'SHREECEM.BO', 'UPL.BO', 'BPCL.BO', 'IOC.BO', 'HINDALCO.BO', 'ADANIGREEN.BO', 'ADANITRANS.BO', 'BAJAJ-AUTO.BO', 'BERGEPAINT.BO', 'BIOCON.BO', 'CADILAHC.BO', 'CHOLAFIN.BO', 'COLPAL.BO', 'CONCOR.BO', 'DABUR.BO', 'DMART.BO', 'GAIL.BO', 'GODREJCP.BO', 'HDFCAMC.BO', 'HINDCOPPER.BO', 'IDEA.BO', 'IGL.BO', 'INDIGO.BO', 'JINDALSTEL.BO', 'LICHSGFIN.BO', 'LUPIN.BO', 'MCDOWELL-N.BO', 'MFSL.BO', 'MINDTREE.BO', 'MOTHERSON.BO', 'MPHASIS.BO', 'MRF.BO', 'MUTHOOTFIN.BO', 'NAUKRI.BO', 'PAGEIND.BO', 'PETRONET.BO', 'PIDILITIND.BO', 'PNB.BO', 'POLYCAB.BO', 'PVR.BO', 'RBLBANK.BO', 'SAIL.BO', 'SIEMENS.BO', 'TORNTPHARM.BO', 'TRENT.BO', 'VEDL.BO', 'VOLTAS.BO', 'WHIRLPOOL.BO', 'YESBANK.BO', 'ZEEL.BO', 'ZOMATO.BO', 'PAYTM.BO', 'POLICYBZR.BO', 'DELTACORP.BO', 'GODREJPROP.BO'],
    
    'BSE 200': ['RELIANCE.BO', 'TCS.BO', 'HDFCBANK.BO', 'INFY.BO', 'HINDUNILVR.BO', 'ITC.BO', 'SBIN.BO', 'BHARTIARTL.BO', 'KOTAKBANK.BO', 'LT.BO', 'ASIANPAINT.BO', 'MARUTI.BO', 'NESTLEIND.BO', 'ULTRACEMCO.BO', 'TITAN.BO', 'POWERGRID.BO', 'NTPC.BO', 'ONGC.BO', 'COALINDIA.BO', 'TATAMOTORS.BO', 'BAJFINANCE.BO', 'WIPRO.BO', 'HCLTECH.BO', 'TECHM.BO', 'ADANIPORTS.BO', 'JSWSTEEL.BO', 'TATASTEEL.BO', 'GRASIM.BO', 'EICHERMOT.BO', 'BAJAJFINSV.BO', 'HEROMOTOCO.BO', 'BRITANNIA.BO', 'DIVISLAB.BO', 'DRREDDY.BO', 'CIPLA.BO', 'SUNPHARMA.BO', 'APOLLOHOSP.BO', 'INDUSINDBK.BO', 'AXISBANK.BO', 'ICICIBANK.BO', 'HDFCLIFE.BO', 'SBILIFE.BO', 'BAJAJHLDNG.BO', 'TATACONSUM.BO', 'SHREECEM.BO', 'UPL.BO', 'BPCL.BO', 'IOC.BO', 'HINDALCO.BO', 'ADANIGREEN.BO', 'ADANITRANS.BO', 'BAJAJ-AUTO.BO', 'BERGEPAINT.BO', 'BIOCON.BO', 'CADILAHC.BO', 'CHOLAFIN.BO', 'COLPAL.BO', 'CONCOR.BO', 'DABUR.BO', 'DMART.BO', 'GAIL.BO', 'GODREJCP.BO', 'HDFCAMC.BO', 'HINDCOPPER.BO', 'IDEA.BO', 'IGL.BO', 'INDIGO.BO', 'JINDALSTEL.BO', 'LICHSGFIN.BO', 'LUPIN.BO', 'MCDOWELL-N.BO', 'MFSL.BO', 'MINDTREE.BO', 'MOTHERSON.BO', 'MPHASIS.BO', 'MRF.BO', 'MUTHOOTFIN.BO', 'NAUKRI.BO', 'PAGEIND.BO', 'PETRONET.BO', 'PIDILITIND.BO', 'PNB.BO', 'POLYCAB.BO', 'PVR.BO', 'RBLBANK.BO', 'SAIL.BO', 'SIEMENS.BO', 'TORNTPHARM.BO', 'TRENT.BO', 'VEDL.BO', 'VOLTAS.BO', 'WHIRLPOOL.BO', 'YESBANK.BO', 'ZEEL.BO', 'ZOMATO.BO', 'PAYTM.BO', 'POLICYBZR.BO', 'DELTACORP.BO', 'GODREJPROP.BO', 'ABBOTINDIA.BO', 'ACC.BO', 'ADANIENT.BO', 'ADANIPOWER.BO', 'ALKEM.BO', 'AMBUJACEM.BO', 'APOLLOTYRE.BO', 'ASHOKLEY.BO', 'ASTRAL.BO', 'ATUL.BO', 'AUBANK.BO', 'BANDHANBNK.BO', 'BATAINDIA.BO', 'BEL.BO', 'BEML.BO', 'BERGERPAINT.BO', 'BHEL.BO', 'BOSCHLTD.BO', 'CROMPTON.BO', 'CUMMINSIND.BO', 'DEEPAKNTR.BO', 'DLF.BO', 'ESCORTS.BO', 'EXIDEIND.BO', 'FEDERALBNK.BO', 'FORTIS.BO', 'GLENMARK.BO', 'GODREJIND.BO', 'GODREJPROP.BO', 'HAVELLS.BO', 'HDFCAMC.BO', 'HINDPETRO.BO', 'HINDZINC.BO', 'IBULHSGFIN.BO', 'ICICIGI.BO', 'ICICIPRULI.BO', 'IDFCFIRSTB.BO', 'INDIAMART.BO', 'INDIGO.BO', 'INFIBEAM.BO', 'IRCTC.BO', 'JKCEMENT.BO', 'JUBLFOOD.BO', 'JUSTDIAL.BO', 'KANSAINER.BO', 'LALPATHLAB.BO', 'LARSEN.BO', 'LATENTVIEW.BO', 'LUXIND.BO', 'MANAPPURAM.BO', 'MARICO.BO', 'MCDOWELL-N.BO', 'METROPOLIS.BO', 'MINDTREE.BO', 'MOTHERSON.BO', 'MPHASIS.BO', 'MRF.BO', 'MUTHOOTFIN.BO', 'NAUKRI.BO', 'NMDC.BO', 'OBEROI.BO', 'OFSS.BO', 'PAGEIND.BO', 'PEL.BO', 'PETRONET.BO', 'PIDILITIND.BO', 'PNB.BO', 'POLYCAB.BO', 'PVR.BO', 'RBLBANK.BO', 'SAIL.BO', 'SIEMENS.BO', 'TORNTPHARM.BO', 'TRENT.BO', 'VEDL.BO', 'VOLTAS.BO', 'WHIRLPOOL.BO', 'YESBANK.BO', 'ZEEL.BO', 'ZOMATO.BO', 'PAYTM.BO', 'POLICYBZR.BO', 'DELTACORP.BO', 'GODREJPROP.BO'],
    
    // US Market Indices
    'S&P 500 Top 50': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'UNH', 'JNJ', 'V', 'PG', 'JPM', 'XOM', 'HD', 'CVX', 'MA', 'PFE', 'ABBV', 'BAC', 'KO', 'AVGO', 'PEP', 'TMO', 'COST', 'WMT', 'DHR', 'ABT', 'VZ', 'ACN', 'NFLX', 'ADBE', 'CRM', 'TXN', 'NKE', 'QCOM', 'CMCSA', 'LIN', 'PM', 'NEE', 'RTX', 'HON', 'UNP', 'IBM', 'AMD', 'SPGI', 'LOW', 'AMAT', 'INTU', 'GE'],
    
    'NASDAQ 100': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ORCL', 'ADBE', 'CRM', 'NFLX', 'AMD', 'INTC', 'QCOM', 'AMAT', 'INTU', 'CSCO', 'TXN', 'CMCSA', 'PYPL', 'ISRG', 'GILD', 'BKNG', 'ADP', 'VRTX', 'MDLZ', 'REGN', 'ATVI', 'ILMN', 'AMGN', 'CHTR', 'FISV', 'CTAS', 'KLAC', 'SNPS', 'CDNS', 'MRNA', 'WBA', 'EXC', 'EA', 'NXPI', 'CTSH', 'BIIB', 'IDXX', 'ALGN', 'DXCM', 'MCHP', 'LRCX', 'FAST', 'CSGP', 'ROST', 'PAYX', 'SBUX', 'ADSK', 'VRSN', 'ANSS', 'CPRT', 'CTXS', 'INCY', 'NTES', 'SIRI', 'SWKS', 'TMUS', 'ULTA', 'VRSK', 'WLTW', 'XEL', 'ZM', 'ZS', 'TEAM', 'SPLK', 'OKTA', 'DOCU', 'CRWD', 'DDOG', 'NET', 'SNOW', 'PLTR', 'ROKU', 'PTON', 'ZOOM', 'SQ', 'SHOP', 'TWLO', 'PINS', 'SNAP', 'UBER', 'LYFT', 'ABNB', 'COIN', 'HOOD', 'SOFI', 'RIVN', 'LCID', 'FUBO', 'PENN', 'DKNG', 'MGM', 'WYNN', 'LVS', 'CZR', 'BYD', 'ERI', 'GNOG', 'RSI', 'SKLZ', 'DKNG', 'PENN', 'MGM', 'WYNN', 'LVS', 'CZR', 'BYD', 'ERI', 'GNOG', 'RSI', 'SKLZ'],
    
    'Dow Jones 30': ['AAPL', 'MSFT', 'UNH', 'JNJ', 'V', 'PG', 'JPM', 'XOM', 'HD', 'CVX', 'MA', 'PFE', 'ABBV', 'BAC', 'KO', 'AVGO', 'PEP', 'TMO', 'COST', 'WMT', 'DHR', 'ABT', 'VZ', 'ACN', 'NFLX', 'ADBE', 'CRM', 'TXN', 'NKE', 'QCOM', 'CMCSA'],
    
    'Tech Giants': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'ORCL', 'ADBE', 'CRM', 'NFLX', 'PYPL', 'UBER', 'LYFT', 'ABNB', 'COIN', 'HOOD', 'SOFI'],
    
    'FAANG Stocks': ['AAPL', 'AMZN', 'GOOGL', 'META', 'NFLX'],
    
    'MAGA Stocks': ['MSFT', 'AAPL', 'GOOGL', 'AMZN'],
    
    // European Markets
    'FTSE 100': ['SHEL.L', 'AZN.L', 'HSBA.L', 'ULVR.L', 'DGE.L', 'RIO.L', 'BHP.L', 'BP.L', 'GSK.L', 'VOD.L', 'BT-A.L', 'LLOY.L', 'BARC.L', 'STAN.L', 'TSCO.L', 'SBRY.L', 'MRO.L', 'PRU.L', 'AV.L', 'LGEN.L', 'AAL.L', 'CRDA.L', 'REL.L', 'EXPN.L', 'SMT.L', 'AUTO.L', 'LAND.L', 'CCH.L', 'IMB.L', 'RKT.L', 'PSON.L', 'WTB.L', 'MNG.L', 'ANTO.L', 'GLEN.L', 'FRES.L', 'EVR.L', 'CRH.L', 'KGF.L', 'SPX.L', 'MGGT.L', 'INF.L', 'SDR.L', 'LSEG.L', 'RMV.L', 'SGE.L', 'HL.L', 'BDEV.L', 'TW.L', 'PFC.L', 'RR.L', 'BA.L', 'GKN.L', 'MGGT.L', 'INF.L', 'SDR.L', 'LSEG.L', 'RMV.L', 'SGE.L', 'HL.L', 'BDEV.L', 'TW.L', 'PFC.L', 'RR.L', 'BA.L', 'GKN.L', 'MGGT.L', 'INF.L', 'SDR.L', 'LSEG.L', 'RMV.L', 'SGE.L', 'HL.L', 'BDEV.L', 'TW.L', 'PFC.L', 'RR.L', 'BA.L', 'GKN.L', 'MGGT.L', 'INF.L', 'SDR.L', 'LSEG.L', 'RMV.L', 'SGE.L', 'HL.L', 'BDEV.L', 'TW.L', 'PFC.L', 'RR.L', 'BA.L', 'GKN.L'],
    
    'DAX 40': ['SAP.DE', 'ASML.DE', 'SIE.DE', 'ALV.DE', 'DTE.DE', 'VOW3.DE', 'BMW.DE', 'DAI.DE', 'BAYN.DE', 'BAS.DE', 'MRK.DE', 'ADS.DE', 'VNA.DE', 'RWE.DE', 'EOAN.DE', 'ENR.DE', 'FRE.DE', 'HEN3.DE', 'CON.DE', 'BEI.DE', 'DHER.DE', 'IFX.DE', 'QGEN.DE', 'SHL.DE', 'ZAL.DE', '1COV.DE', 'DB1.DE', 'DBK.DE', 'DPW.DE', 'FME.DE', 'HNR1.DE', 'LIN.DE', 'LHA.DE', 'MTX.DE', 'PUM.DE', 'RHM.DE', 'SDF.DE', 'TKA.DE', 'VOW3.DE', 'WCH.DE'],
    
    // Emerging Markets
    'Brazil Bovespa': ['VALE3.SA', 'PETR4.SA', 'ITUB4.SA', 'BBDC4.SA', 'ABEV3.SA', 'WEGE3.SA', 'MGLU3.SA', 'SUZB3.SA', 'RENT3.SA', 'LREN3.SA'],
    
    'China A-Shares': ['000001.SZ', '000002.SZ', '000858.SZ', '002415.SZ', '300059.SZ', '600036.SS', '600519.SS', '600887.SS', '601318.SS', '601398.SS'],
    
    'South Korea KOSPI': ['005930.KS', '000660.KS', '035420.KS', '207940.KS', '006400.KS', '051910.KS', '068270.KS', '035720.KS', '323410.KS', '105560.KS']
  }

  const handleAnalyze = () => {
    // Parse input - supports comma, space, newline separated
    const tickers = inputText
      .split(/[,\s\n]+/)
      .map(t => t.trim().toUpperCase())
      .filter(t => t.length > 0)

    if (tickers.length === 0) {
      setError('Please enter at least one ticker symbol')
      return
    }

    if (tickers.length > 50) {
      setError('Maximum 50 tickers allowed per analysis')
      return
    }

    setError('')
    onAnalyze(tickers, mode)
  }

  const loadPreset = (listName: string) => {
    const tickers = presetLists[listName as keyof typeof presetLists]
    setInputText(tickers.join(', '))
    setError('')
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      setInputText(text)
      setError('')
    }
    reader.readAsText(file)
  }

  const exampleText = `Example formats:
• RELIANCE.NS, TCS.NS, INFY.NS
• AAPL MSFT GOOGL
• One per line:
  HDFCBANK.NS
  ICICIBANK.NS`

  return (
    <div className="space-y-6">
      {/* Mode Selection */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Analysis Mode</h3>
        <div className="flex space-x-4">
          <button
            onClick={() => setMode('buy')}
            className={`flex-1 px-6 py-3 rounded-lg font-medium transition-colors ${
              mode === 'buy'
                ? 'bg-green-600 text-white'
                : 'bg-white border-2 border-slate-300 text-slate-700 hover:border-green-600'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <span className="text-2xl">🐂</span>
              <span>Buy Opportunities</span>
            </div>
            <div className="text-sm mt-1 opacity-80">Find undervalued stocks</div>
          </button>
          
          <button
            onClick={() => setMode('sell')}
            className={`flex-1 px-6 py-3 rounded-lg font-medium transition-colors ${
              mode === 'sell'
                ? 'bg-red-600 text-white'
                : 'bg-white border-2 border-slate-300 text-slate-700 hover:border-red-600'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <span className="text-2xl">🐻</span>
              <span>Sell Signals</span>
            </div>
            <div className="text-sm mt-1 opacity-80">Identify overvalued positions</div>
          </button>
        </div>
      </div>

      {/* Input Methods */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Input Stock Symbols</h3>
        
        {/* Preset Lists */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Quick Start - Load Preset List
          </label>
          <div className="flex gap-4 items-center">
            <select
              onChange={(e) => {
                if (e.target.value) {
                  loadPreset(e.target.value)
                  e.target.value = '' // Reset dropdown
                }
              }}
              className="px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-sm min-w-[200px]"
                disabled={loading}
              defaultValue=""
            >
              <option value="" disabled>Select a preset list...</option>
              <optgroup label="🇮🇳 NIFTY Indices">
                <option value="NIFTY 50">NIFTY 50</option>
                <option value="NIFTY Next 50">NIFTY Next 50</option>
                <option value="NIFTY 100">NIFTY 100</option>
                <option value="NIFTY 200">NIFTY 200</option>
              </optgroup>
              <optgroup label="🏦 Sectoral Indices">
                <option value="Bank Nifty">Bank Nifty</option>
                <option value="NIFTY IT">NIFTY IT</option>
                <option value="NIFTY Pharma">NIFTY Pharma</option>
                <option value="NIFTY Auto">NIFTY Auto</option>
                <option value="NIFTY FMCG">NIFTY FMCG</option>
                <option value="NIFTY Metal">NIFTY Metal</option>
                <option value="NIFTY Energy">NIFTY Energy</option>
                <option value="NIFTY Realty">NIFTY Realty</option>
                <option value="NIFTY Media">NIFTY Media</option>
                <option value="NIFTY PSU Bank">NIFTY PSU Bank</option>
                <option value="NIFTY Private Bank">NIFTY Private Bank</option>
              </optgroup>
              <optgroup label="📊 Market Cap Categories">
                <option value="Large Cap">Large Cap</option>
                <option value="Mid Cap">Mid Cap</option>
                <option value="Small Cap">Small Cap</option>
              </optgroup>
              <optgroup label="🇮🇳 BSE Indices">
                <option value="BSE Sensex">BSE Sensex</option>
                <option value="BSE 100">BSE 100</option>
                <option value="BSE 200">BSE 200</option>
              </optgroup>
              <optgroup label="🇺🇸 US Market Indices">
                <option value="S&P 500 Top 50">S&P 500 Top 50</option>
                <option value="NASDAQ 100">NASDAQ 100</option>
                <option value="Dow Jones 30">Dow Jones 30</option>
                <option value="Tech Giants">Tech Giants</option>
                <option value="FAANG Stocks">FAANG Stocks</option>
                <option value="MAGA Stocks">MAGA Stocks</option>
              </optgroup>
              <optgroup label="🇪🇺 European Markets">
                <option value="FTSE 100">FTSE 100</option>
                <option value="DAX 40">DAX 40</option>
              </optgroup>
              <optgroup label="🌍 Emerging Markets">
                <option value="Brazil Bovespa">Brazil Bovespa</option>
                <option value="China A-Shares">China A-Shares</option>
                <option value="South Korea KOSPI">South Korea KOSPI</option>
              </optgroup>
            </select>
            <div className="text-xs text-slate-500">
              {Object.keys(presetLists).length} preset lists available
            </div>
          </div>
        </div>

        {/* Text Input */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Manual Entry (comma, space, or newline separated)
          </label>
          <textarea
            value={inputText}
            onChange={(e) => {
              setInputText(e.target.value)
              setError('')
            }}
            placeholder={exampleText}
            className="w-full h-40 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            disabled={loading}
          />
          <div className="flex justify-between items-center mt-2">
            <p className="text-xs text-slate-500">
              {inputText.split(/[,\s\n]+/).filter(t => t.trim().length > 0).length} tickers entered (max 50)
            </p>
            <button
              onClick={() => setInputText('')}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={loading}
            >
              Clear All
            </button>
          </div>
        </div>

        {/* File Upload */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Or Upload File (.txt, .csv)
          </label>
          <label className="flex items-center justify-center w-full h-20 px-4 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors">
            <div className="flex flex-col items-center">
              <Icons.DocumentText className="w-8 h-8 text-slate-400 mb-1" />
              <span className="text-sm text-slate-600">Click to upload or drag file here</span>
            </div>
            <input
              type="file"
              className="hidden"
              accept=".txt,.csv"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <Icons.AlertTriangle className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Analyze Button */}
        <button
          onClick={handleAnalyze}
          disabled={loading || inputText.trim().length === 0}
          className="w-full px-6 py-4 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Icons.ChartPie className="w-5 h-5" />
              <span>Analyze & Rank Stocks</span>
            </>
          )}
        </button>
      </div>

      {/* Tips */}
      <div className="card p-6 bg-blue-50 border-blue-200">
        <div className="flex items-start">
          <Icons.Star className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-blue-900 mb-2">Pro Tips</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Indian stocks: Add .NS suffix (e.g., RELIANCE.NS)</li>
              <li>• BSE stocks: Add .BO suffix (e.g., RELIANCE.BO)</li>
              <li>• US stocks: Use plain ticker (e.g., AAPL, MSFT)</li>
              <li>• Analysis takes ~10-15 seconds per stock</li>
              <li>• Results are cached for faster subsequent lookups</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

