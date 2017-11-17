import boto3
import botocore
import click
import re
from fspk_log import Log
from fspk_s3_utils import S3Utils

SEMVER_REGEX = '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?(\+[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*)?$'
ENCODED_SEMVER_REGEX = re.sub('\.', '_',  SEMVER_REGEX)

class FPCommon(Log):

    def __init__(self, region=None, debug=False, stage='dev', fp_stage='prod'):
        sess = boto3.session.Session()
        default_region = sess.region_name
        self._region = default_region if(region is None) else region
        self._session = boto3.setup_default_session(region_name=self._region)
        self._sts = boto3.client('sts')
        self._s3r = boto3.resource('s3')
        self._s3 = boto3.client('s3')
        self._lmda = boto3.client('lambda')
        self._iam = boto3.client('iam')
        self._apig = boto3.client('apigateway')

        self._stage = stage
        self._fp_stage = fp_stage
        self._aws_account_id = self.get_aws_account_id()
        self._s3utils = S3Utils(debug)
        super(FPCommon, self).__init__(debug)

    def semverEncode(self, semver):
        return re.sub('\.', '_', semver)

    def semverDecode(self, encodedSemver):
        return re.sub('_', '.', encodedSemver)

    def semverMatch(self, input, encoded=True):
        regex = ENCODED_SEMVER_REGEX if(encoded) else SEMVER_REGEX
        m = re.match(regex, input)
        if(m is not None):
            return m.group()
        else:
            return None

    def fp_bucket(self, region_override=None):
        region = region_override if(region_override is not None) else self._region
        settings = {
            'region': region,
            'fp_stage': self._fp_stage
        }
        return 'faaspack-%(fp_stage)s-%(region)s' % settings

    def fp_latest_version(self, name, prefix):
        prefixes = self._s3utils.fetchPartitionPrefixes(self.fp_bucket(), prefix, '/')
        self.debug('prefixes: %s' % prefixes)
        if(len(prefixes) == 0):
            return None
        else:
            return prefixes[-1].split('/')[1]

    def fp_key_prefix(self, name, scope):
        prefix = '' if scope is None else "%(scope)s/"
        return '%(prefix)s%(name)s' % locals()

    def fp_conf_key(self, name, version, scope):
        keyPrefix = self.fp_key_prefix(name, scope)
        return "%(keyPrefix)s/%(version)s/faaspack_conf" % locals()

    def fp_upload_conf(self, conf, name, version, scope=None):
        key = self.fp_conf_key(name, version, scope)
        bucket = self.fp_bucket('us-east-1') # always upload to us-east-1
        obj = self._s3r.Object(bucket, key)
        obj.put(Body=conf)

    def fp_zip_key(self, name, version, scope=None):
        keyPrefix = self.fp_key_prefix(name, scope)
        return "%(keyPrefix)s/%(version)s/faaspack_zip" % locals()

    def fp_upload_zip(self, zipfile, name, version, scope=None):
        key = self.fp_zip_key(name, version, scope)
        bucket = self.fp_bucket('us-east-1') # always upload to us-east-1
        obj = self._s3r.Object(bucket, key)
        obj.put(Body=zipfile)

    def fp_download_conf(self, name, version, scope=None):
        # TODO check profile has access if private
        keyPrefix = self.fp_key_prefix(name, scope)
        if(version == 'latest'):
            realVersion = self.fp_latest_version(name, keyPrefix+'/')
            keyPrefix = "%(keyPrefix)s/%(realVersion)s" % locals()
        else:
            keyPrefix = "%(keyPrefix)s/%(version)s" % locals()

        key = '%(keyPrefix)s/faaspack_conf' % locals()
        self.debug("key: %s" % key)
        bucket = self.fp_bucket('us-east-1') # always download to us-east-1
        res = self._s3.get_object(
            Bucket=bucket,
            Key='%(keyPrefix)s/faaspack_conf' % locals()
        )
        self.debug('download res: %s' % res)
        return res['Body'].read()


    def fp_check_exists(self, name, version, scope=None):
        # TODO check profile has access if private
        key_prefix = self.fp_key_prefix(name, scope)
        self.debug("key_prefix: %s" % key_prefix)
        if(version == 'latest'):
            if(self.fp_latest_version(name, key_prefix+'/') is None):
                return False
            else:
                return True
        else:
            try:
                key = key_prefix+'/'+version+'/faaspack_conf'
                self.debug("key: %s" % key)
                self._s3.head_object(
                    Bucket=self.fp_bucket(),
                    Key=key
                )
                return True
            except botocore.exceptions.ClientError:
                return False


    def fp_name_split(self, name):
        scope = None
        if(name.startswith('@')):
            nameParts = name.spllit('/')
            if(len(nameParts) != 2):
                exit("Invalid FaaSPack name format.  Expected: [<@scope>/]<name>")
            elif(len(nameParts[0]) < 2 or len(nameParts[1]) < 1):
                exit("Invalid FaaSPack name format.  Expected: [<@scope>/]<name>")
            else:
                scope = nameParts[0][1:] # remove leading @
                name = nameParts[1]
        return name, scope

    def get_bucket_region(self, bucket):
        res = self._s3r.meta.client.get_bucket_location(Bucket=bucket)["LocationConstraint"]
        if(res is None):
            return 'us-east-1'
        else:
            return res

    def get_default_region(self):
        return self._region

    def get_aws_account_id(self):
        return self._sts.get_caller_identity()['Account']

    def get_brand(self):
        return "FaaSPack"
