import boto3
import botocore
import json
import time
import click

class FPLambda:

    def __init__(self, fp_common):
        self._fp_common = fp_common

    def check_lambda_exists(self, lambda_name):
        try:
            self._fp_common._lmda.get_function(FunctionName=lambda_name)
            return True
        except botocore.exceptions.ClientError:
            return False

    def list_lambda_versions(self, lambda_name):
        if(not self.check_lambda_exists(lambda_name)):
            return []
        else:
            res = self._fp_common._lmda.list_aliases(
                FunctionName=lambda_name
            )
            versions = []
            for alias in res['Aliases']:
                name = alias['Name']
                if(name != 'current'):
                    versions.append(self._fp_common.semverDecode(name))
            return versions

    def get_current_lambda_version(self, lambda_name):
        if(not self.check_lambda_exists(lambda_name)):
            return None
        else:
            res = self._fp_common._lmda.list_aliases(
                FunctionName=lambda_name
            )
            aliases = res['Aliases']
            # find 'current' alias
            current = filter(lambda a: a['Name'] == 'current', aliases)
            if(len(current) == 0):
                self._fp_common.error("'current' alias does not exist for %(lambda_name)s" % locals())
            current = current[0]

            # match current with version by FunctionVersion
            version = filter(lambda a: a['FunctionVersion'] == current['FunctionVersion'], aliases)
            if(len(version) > 0):
                return self._fp_common.semverDecode(version[0]['Name'])
            else:
                return None

    def check_lambda_version_exists(self, lambda_name, version):
        encodedSemver = self._fp_common.semverEncode(version)
        if(self.check_lambda_exists(lambda_name)):
            try:
                res = self._fp_common._lmda.get_alias(FunctionName=lambda_name, Name=encodedSemver)
                return True
            except botocore.exceptions.ClientError:
                return False
        else:
            return False

    def check_iam_role_exists(self, role_name):
        try:
            self._fp_common._iam.get_role(RoleName=role_name)
            return True
        except botocore.exceptions.ClientError:
            return False

    def iam_role_arn(self, role_name):
        return self._fp_common._iam.get_role(RoleName=role_name)['Role']['Arn']

    def attach_role_policy(self, role_name, policy_arn):
        return self._fp_common._iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )

    def create_basic_iam_role(self, lambda_name):
        brand = self._fp_common.get_brand()
        role = self._fp_common._iam.create_role(
            RoleName=lambda_name,
            AssumeRolePolicyDocument=self.default_assume_role_policy_doc(),
            Description='Role for %(lambda_name)s. Created by %(brand)s' % locals()
        )
        self.attach_role_policy(
            role['Role']['RoleName'],
            'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )
        # wait for IAM role to provision across all regions
        self._fp_common.info("Creating IAM Role: %(lambda_name)s. Waiting for cross-region propagation..." % locals())
        time.sleep(10)
        self._fp_common.info("Done")
        return role['Role']['Arn']

    def create_lambda_function(self, lambda_name, version, runtime, handler, description, timeout=10, memory_size=128, env={}, tags={}):
        if(self.check_iam_role_exists(lambda_name)):
            role = self.iam_role_arn(lambda_name)
        else:
            role = self.create_basic_iam_role(lambda_name)
        deploy_region = self._fp_common.get_default_region()
        account_id = self._fp_common.get_aws_account_id()
        brand = self._fp_common.get_brand()
        bucket = self._fp_common.fp_bucket()
        zip_key = self._fp_common.fp_zip_key(lambda_name, version)
        self._fp_common.debug("bucket: %(bucket)s, key: %(zip_key)s" % locals())
        # create function
        res = self._fp_common._lmda.create_function(
            FunctionName=lambda_name,
            Runtime=runtime,
            Role=role,
            Handler=handler,
            Code={
                'S3Bucket':bucket,
                'S3Key':zip_key
            },
            Description='%(lambda_name)s. Created by %(brand)s' % locals(),
            Timeout=timeout,
            MemorySize=memory_size,
            Publish=True,
            Environment=env,
            Tags=tags
        )

        # create 'current' alias
        self.create_lambda_alias(
            lambda_name,
            'current',
            res['Version'],
            'The current version of the function'
        )

        # create semver based alias
        encodedSemver = self._fp_common.semverEncode(version)
        self.create_lambda_alias(
            lambda_name,
            encodedSemver,
            res['Version'],
            'alias for version: %s' % version
        )


    def create_lambda_alias(self, lambda_name, alias, function_version, desc=''):
        # create alias
        return self._fp_common._lmda.create_alias(
            FunctionName=lambda_name,
            Name=alias,
            FunctionVersion=function_version,
            Description=desc
        )

    def update_lambda_function(self, lambda_name, version):
        bucket = self._fp_common.fp_bucket()
        zip_key = self._fp_common.fp_zip_key(lambda_name, version)
        # update function
        return self._fp_common._lmda.update_function_code(
            FunctionName=lambda_name,
            S3Bucket=bucket,
            S3Key=zip_key,
            Publish=True,
        )

    def update_alias_to_version(self, lambda_name, alias, version):
        encodedSemver = self._fp_common.semverEncode(version)
        # fetch semver alias lambda version
        res = self._fp_common._lmda.get_alias(
            FunctionName=lambda_name,
            Name=encodedSemver
        )
        func_version = res['FunctionVersion']
        return self.update_lambda_alias(lambda_name, alias, func_version)

    def update_lambda_alias(self, lambda_name, alias, function_version):
        return self._fp_common._lmda.update_alias(
            FunctionName=lambda_name,
            Name=alias,
            FunctionVersion=function_version
        )

    def default_assume_role_policy_doc(self):
        # note: multiline string below
        return (
            '{'
              '"Version": "2012-10-17",'
              '"Statement": ['
                '{'
                  '"Effect": "Allow",'
                  '"Principal": {'
                    '"Service": "lambda.amazonaws.com"'
                  '},'
                  '"Action": "sts:AssumeRole"'
                '}'
              ']'
            '}'
        )
