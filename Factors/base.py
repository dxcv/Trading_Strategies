import httplib
import urllib
import json
import traceback
import pandas as pd


class Client:
    HTTP_OK = 200
    HTTP_AUTHORIZATION_ERROR = 401

    domain = 'api.wmcloud.com'
    port = 443
    token = ''
    httpClient = None

    def __init__( self ):
        self.httpClient = httplib.HTTPSConnection(self.domain, self.port)

    def __del__( self ):
        if self.httpClient is not None:
            self.httpClient.close()

    def encodepath(self, path):
        start=0
        n=len(path)
        re=''
        i=path.find('=',start)
        while i!=-1 :
            re+=path[start:i+1]
            start=i+1
            i=path.find('&',start)
            if(i>=0):
                for j in range(start,i):
                    if(path[j]>'~'):
                        re+=urllib.quote(path[j])
                    else:
                        re+=path[j]
                re+='&'
                start=i+1
            else:
                for j in range(start,n):
                    if(path[j]>'~'):
                        re+=urllib.quote(path[j])
                    else:
                        re+=path[j]
                start=n
            i=path.find('=',start)
        return re

    def init(self, token):
        self.token=token

    def getData(self, path):
        result = None
        path='/data/v1'+path
        path=self.encodepath(path)
        try:
            #set http header here
            self.httpClient.request('GET', path, headers = {"Authorization": "Bearer " + self.token})
            #make request
            response = self.httpClient.getresponse()
            #read result
            if response.status == self.HTTP_OK:
                #parse json into python primitive object
                result = response.read()
            else:
                result = response.read()
            if(path.find('.csv?')!=-1):
                result=result.decode('GB2312').encode('utf-8')
            return response.status, result
        except Exception, e:
            #traceback.print_exc()
            raise e
        return -1, result

class Downloader :
    TOKEN = '20353207bd1bb251c0512ffa4a4fc28de0f6bf16bbdb41c89cb2b4ab8c458551'

    form_cf = 'getFdmtCF.json'
    form_earning_report = '/api/fundamental/getFdmtEe.json'
    form_is = '/api/fundamental/getFdmtIS.json'
    form_is_latest = '/api/fundamental/getFdmtISAllLatest.json'
    form_mkt_eq = '/api/market/getMktEqud.json'
    form_mkt_eq_adj = '/api/market/getMktEqudAdj.json'

    client = None

    def __init__(self, token=None) :
        if token is not None:
            self.TOKEN = token
        if self.client is None:
            self.client = Client()
            self.client.init(self.TOKEN)

    def getData(self, form, params) :
        try:
            ticker = params.get('ticker')
            if ticker is None:
                print 'ticker is none'
                return None

            field = params.get('field')
            if field is None:
                field = ''

            secID = params.get('secID')
            if secID is None:
                secID = ''

            beginDate = params.get('beginDate')
            endDate = params.get('endDate')
            if (beginDate is None) or (endDate is None) :
                beginDate_str = ''
                endDate_str = ''
            else :
                beginDate_str = beginDate.strftime('%Y%m%d')
                endDate_str = endDate.strftime('%Y%m%d')

            url1='{form}?field={field}&secID={secID}&ticker={ticker}&beginDate={beginDate}&endDate={endDate}'\
                .format(form=form, field=field, secID = secID, ticker=ticker, \
                        beginDate=beginDate_str, endDate=endDate_str)
            print url1

            code, result = self.client.getData(url1)
            if code==200:
                result = json.loads(result)
                df = pd.DataFrame(result['data'])
                #df['publishDate'] = pd.to_datetime(df['publishDate'])
                #df.rename(columns={'publishDate':'date'}, inplace=True)
                #df.set_index('date', inplace=True)
                return df
            else:
                print code
                print result

                return None

        except Exception, e:
            #traceback.print_exc()
            raise e



class FactorFactory :

    def __init__(self):
        pass

    def getFactor_EP(self, downloader, params) :
        # 1. download the related data
        f_is = downloader.getData(downloader.form_is, params) # from Income Statement
        f_is = f_is.sort(['publishDate', 'reportType'])
        f_is.drop_duplicates('publishDate', inplace=True)
        f_is = f_is.set_index('publishDate').sort()

        # 2. cleaning earning data.
        f_earning = f_is[['reportType', 'NIncome']]
        f_earning.loc[:, 'Earning_Q'] = f_earning.loc[:, 'NIncome'] - f_earning.loc[:,'NIncome'].shift(1)
        f_earning.head()
        index_q1 = f_earning.loc[:, 'reportType'] == 'Q1'
        index_a = f_earning.loc[:, 'reportType'] == 'A'
        f_earning.loc[index_q1, 'Q'] = f_earning.loc[index_q1, 'NIncome']
        f_earning.loc[:,'Earning_TTM'] = pd.rolling_sum(f_earning['Earning_Q'], 4)
        f_earning.loc[:, 'Earning_FY0'] = f_earning.loc[:, 'Earning_Q'] * 4
        f_earning.loc[:, 'Earning_LY'] = f_earning.loc[index_a, 'NIncome']

        # 3. download price and other information
        f_price = downloader.getData(downloader.form_mkt_eq, params)
        f_price = f_price.set_index('tradeDate').sort()

        # 4. create EP data
        f_ep = f_price[['marketValue']]
        f_ep = f_ep.join(f_earning[['Earning_Q', 'Earning_TTM', 'Earning_FY0', 'Earning_LY']], how='outer')
        f_ep = f_ep.ffill().dropna()

        f_ep.rename(columns = {'marketValue' : 'MV'}, inplace=True)

        f_ep['EP_TTM'] = f_ep['Earning_TTM'] / f_ep['MV']
        f_ep['EP_FY0'] = f_ep['Earning_FY0'] / f_ep['MV']
        f_ep['EP_LY'] = f_ep['Earning_LY'] / f_ep['MV']
        f_ep['PE_TTM'] = 1/f_ep['EP_TTM']
        return f_ep


from datetime import datetime
import matplotlib

if __name__ == '__main__' :
    ff = FactorFactory()
    dd = Downloader()

    params = {}
    params['ticker'] = '000001'
    #params['beginDate'] = datetime.strptime('20080101', '%Y%m%d')
    params['endDate'] = datetime.today()

    ep = ff.getFactor_EP(dd, params)
    print ep.columns