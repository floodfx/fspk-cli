import boto3
from fspk_log import Log

class S3Utils(Log):

    def __init__(self, debug=False):
        self._s3 = boto3.client('s3')
        super(S3Utils, self).__init__(debug)

    def fetchPartitionItems(self, bucket, prefix, delimiter, resultProcessor, continuationToken=None):
        items = []
        params = {
            'Bucket': bucket,
            'Prefix': prefix
        }
        self.debug("params: %s" % params)
        if(delimiter is not None):
            params['Delimiter'] = delimiter

        if(continuationToken is not None):
            params['ContinuationToken'] = continuationToken

        res = self._s3.list_objects_v2(**params)
        items = resultProcessor(res)
        if('ContinuationToken' in res.keys()):
            return items + self.fetchPartitionItems(bucket, prefix, delimiter, resultProcessor, res['ContinuationToken'])
        else:
            return items


    def fetchPartitionPrefixes(self, bucket, prefix, delimiter, continuationToken=None):
        def processResults(res):
            self.debug("results: %s" % res)
            if('CommonPrefixes' in res.keys()):
                return map(lambda prefix: prefix['Prefix'], res['CommonPrefixes'])
            else:
                return []
        return self.fetchPartitionItems(bucket, prefix, delimiter, processResults, continuationToken)

    def fetchPartitionKeys(self, bucket, prefix, delimiter, continuationToken=None):
        def processResults(res):
            return res['Contents'].map(lambda content: content['Key'])
        return self.fetchPartitionItems(bucket, prefix, delimiter, processResults, continuationToken)
