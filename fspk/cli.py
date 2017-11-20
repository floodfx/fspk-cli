from fspk_common import FPCommon
from fspk_apig import FPApig
from fspk_lambda import FPLambda
import click
import yaml

__version__ = "0.0.4"

@click.group()
def fp():
    click.echo("FaaSPack Tool: Version [%s]" % __version__)
    pass

# checks for existing install.  creates if not, updates if so
@click.command(help='Install a given FaaSPack.')
@click.argument('name')
@click.option('-v', '--version', default='latest', help='version to install')
@click.option('-s', '--stage', default='dev', help='stage for install. typically: prod or dev')
@click.option('-m', '--memory', default=128, help='amount of memory (MB) to provision for FaaSPack')
@click.option('-t', '--timeout', default=10, help='time (seconds) before FaaSPack should timeout')
@click.option('-r', '--region', default='us-east-1', help='region for install. defaults to profile setting')
@click.option('-d', '--debug', is_flag=True, help='print debugging messages')
@click.option('-o', '--mode', default='prod', help='mode of operation [unusual to change]')
def install(name, version, stage, memory, timeout, region, debug, mode): #, cloud, profile):
    fp_common = FPCommon(region, debug, stage, mode)

    if(not region in ['us-east-1', 'us-west-2']):
        fp_common.error("Currently FaaSPack only supports regions 'us-east-1' and 'us-west-2'.", True)

    fp_common.info("Installing FaaSPack - name: %(name)s, version: %(version)s, stage: %(stage)s to region: %(region)s" % locals())
    # split name into scope and name
    name, scope = fp_common.fp_name_split(name)

    # check FaaSPack for 'name' and 'version' exists
    exists = fp_common.fp_check_exists(name, version, scope)
    if(not exists):
        fp_common.error("Version (%(version)s) of FaaSPack (%(name)s) was not found." % locals(), True)

    # download FaasPack config
    conf = fp_common.fp_download_conf(name, version, scope)
    fp_common.debug("Configuration for FaasPack - name: %(name)s, version: %(version)s" % locals())
    fp_common.debug(conf)
    # parse config yaml
    confDict = yaml.load(conf)

    # read conf version and overwrite input version (which could be 'latest')
    confVersion = confDict['version']
    if(version == 'latest'):
        fp_common.info('\'latest\' version => %s' % confVersion)
        version = confVersion

    fp_common.info("Found FaasPack - name: %(name)s, version: %(version)s" % locals())

    # check for existing installation
    fp_lambda = FPLambda(fp_common)
    lambda_exists = fp_lambda.check_lambda_exists(name)
    if(lambda_exists):
        fp_common.info("'%(name)s' already installed... checking version..." % locals())
        lambda_version_exists = fp_lambda.check_lambda_version_exists(name, version)
        if(lambda_version_exists):
            fp_common.info("'%(name)s', version: %(version)s already installed. Nothing to do." % locals())
            fp_common.exit()
        else:
            fp_common.info("'%(name)s', version: %(version)s not installed.  Updating..." % locals())
            # update lambda function to new version
            res = fp_lambda.update_lambda_function(
                name,
                version
            )
            fp_common.debug("res: %s" % res)
            encodedSemver = fp_common.semverEncode(version)
            ares = fp_lambda.create_lambda_alias(name, encodedSemver, res['Version'])
            fp_common.debug("ares: %s" % ares)
    else:
        # create lambda function
        # but first ask for gather env
        env = {}
        if('env' in confDict.keys()):
            for e in confDict['env']:
                prompt_description = "- %s" % e['description'] if('description' in e.keys()) else ''
                prompt_name = e['name']
                prompt = "%(prompt_name)s %(prompt_description)s" % locals()
                data = sanitised_input(prompt, '')
                env[e['name']] = data

        # now create
        description = name if(not 'description' in confDict.keys()) else confDict['description']
        fp_lambda.create_lambda_function(
            name,
            version,
            'nodejs6.10',
            'index.handle',
            description,
            timeout,
            memory,
            {
                'Variables': env
            },
            {
                'faaspack_name': name
            }
        )
        # check for additional iam settings
        iam_statements = []
        if('aws' in confDict.keys() and 'iam' in confDict['aws'].keys()):
            for r in confDict['aws']['iam']:
                statement = {
                    'Effect': r['Effect'],
                    'Action': r['Action'],
                    'Resource': r['Resource']
                }
                iam_statements.append(statement)
        fp_common.debug("iam statements: %s" % iam_statements)
        # create inline policy if iam statements
        if(len(iam_statements) > 0):
            policy_name = '%(name)s-inline-policy' % locals()
            fp_lambda.put_role_policy(name, policy_name, iam_statements)

        # install apig if needed
        if('http-trigger' in confDict and confDict['http-trigger'] == True):
            fp_apig = FPApig(fp_common)
            apig_exists = fp_apig.check_apig_exists(name)
            fp_common.debug("apig exists? %s" % apig_exists)
            if(not apig_exists):
                fp_apig.create_apig_lambda_proxy(
                     name,
                     name
                )


@click.command(help="Updates 'current' alias to given version.")
@click.argument('name')
@click.argument('version')
@click.option('-s', '--stage', default='dev', help='stage for install. typically: prod or dev')
@click.option('-r', '--region', default='us-east-1', help='region for install')
@click.option('-d', '--debug', is_flag=True, help='print debugging messages')
@click.option('-o', '--mode', default='prod', help='mode of operation [unusual to change]')
def update(name, version, stage, region, debug, mode):
    fp_common = FPCommon(region, debug, stage, mode)
    if(not region in ['us-east-1', 'us-west-2']):
        fp_common.error("Currently FaaSPack only supports regions 'us-east-1' and 'us-west-2'.", True)

    fp_lambda = FPLambda(fp_common)

    fp_common.info("Updating FaaSPack - name: %(name)s, to version: %(version)s, stage: %(stage)s in region: %(region)s" % locals())

    # split name into scope and name
    name, scope = fp_common.fp_name_split(name)

    # ensure faaspack installed
    lambda_exists = fp_lambda.check_lambda_exists(name)
    if(not lambda_exists):
        fp_common.error("No version of '%(name)s' is installed." % locals(), True)

    # ensure faaspack version installed
    lambda_version_exists = fp_lambda.check_lambda_version_exists(name, version)
    if(not lambda_version_exists):
        fp_common.error("Version '%(version)s' of FaaSPack '%(name)s' was not installed." % locals(), False)
        # list installed versions
        versions = fp_lambda.list_lambda_versions(name)
        p_versions = "[%s]" % ', '.join(versions)
        fp_common.error("Installed versions: %(p_versions)s" % locals(), True)

    # check if already pointing at that version
    current_version = fp_lambda.get_current_lambda_version(name)
    fp_common.info("Current version: %(current_version)s" % locals())
    if(current_version == version):
        fp_common.info("'%(name)s' is already at target version: %(version)s" % locals())
        fp_common.exit()

    # update 'current' alias to the new version
    # TODO if change in MAJOR or MINOR semver, re-prompt for env inputs?
    fp_lambda.update_alias_to_version(name, 'current', version)
    fp_common.info("Updated FaaSPack - name: %(name)s, to version: %(version)s" % locals())


@click.command(help="Configures 'current' version of FaaSPack")
@click.argument('name')
@click.option('-s', '--stage', default='dev', help='stage for install. typically: prod or dev')
@click.option('-m', '--memory', default=None, help='amount of memory (MB) to provision for FaaSPack')
@click.option('-t', '--timeout', default=None, help='time (seconds) before FaaSPack should timeout')
@click.option('-r', '--region', default='us-east-1', help='region for install')
@click.option('-d', '--debug', is_flag=True, help='print debugging messages')
@click.option('-o', '--mode', default='prod', help='mode of operation [unusual to change]')
def configure(name, stage, memory, timeout, region, debug, mode):
    fp_common = FPCommon(region, debug, stage, mode)
    if(not region in ['us-east-1', 'us-west-2']):
        fp_common.error("Currently FaaSPack only supports regions 'us-east-1' and 'us-west-2'.", True)

    fp_lambda = FPLambda(fp_common)

    fp_common.info("Configuring FaaSPack - name: %(name)s, stage: %(stage)s in region: %(region)s" % locals())

    # split name into scope and name
    name, scope = fp_common.fp_name_split(name)

    # ensure faaspack installed
    lambda_exists = fp_lambda.check_lambda_exists(name)
    if(not lambda_exists):
        fp_common.error("No version of '%(name)s' is installed." % locals(), True)

    # get current version
    current_version = fp_lambda.get_current_lambda_version(name)
    fp_common.info("Current version: %(current_version)s" % locals())

    # get configuration for current version
    conf = fp_common.fp_download_conf(name, current_version, scope)
    fp_common.debug("Configuration for FaasPack - name: %(name)s, version: %(current_version)s" % locals())
    fp_common.debug(conf)
    # parse config yaml
    confDict = yaml.load(conf)

    # current configration
    currentConf = fp_lambda.get_current_lambda_configuration(name)
    fp_common.debug("currentConf %s" % currentConf)

    # ask for input
    env = {}
    if('env' in confDict.keys()):
        for e in confDict['env']:
            fp_common.debug("%s" % e)
            prompt_description = "- %s" % e['description'] if('description' in e.keys()) else ''
            prompt_name = e['name']
            prompt_default = currentConf[prompt_name] if(prompt_name in currentConf.keys()) else None
            prompt = "%(prompt_name)s %(prompt_description)s" % locals()
            data = sanitised_input(prompt, prompt_default)
            env[e['name']] = data

    # first update function code to use current version code
    # this ensures $LATEST is the right code...
    code_res = fp_lambda.update_lambda_function_code_to_current(name)
    # now update configuration
    res = fp_lambda.update_lambda_configuration(name, env, memory, timeout)
    # finally publish
    res = fp_lambda.publish_lambda_code_and_config(name, code_res['CodeSha256'])
    published_version = res['Version']
    # and update version and current alias to point at new published version
    encodedSemver = fp_common.semverEncode(current_version)
    res = fp_lambda.update_lambda_alias(name, encodedSemver, published_version)
    res = fp_lambda.update_lambda_alias(name, 'current', published_version)
    # TODO clean up old versions?


# @click.command(help="Removes FaaSPack from your cloud")
# @click.argument('name')
# @click.option('-f', '--force', default=False, help="Do not warn me.")
# def uninstall(name, force):
#    fp_common.info("About to remove FaaSPack %(name)s from your cloud" % locals())

#def uninstall():
#    fp_common.info('Uninstalling')

    # delete apig

    # delete lambda

    # delete iam role

@click.command(help="Publishes FaaSPack")
@click.option('-z', '--zip', default='./faaspack.zip', help="the FaaSPack zip file")
@click.option('-d', '--debug', is_flag=True, help='print debugging messages')
@click.option('-o', '--mode', default='prod', help='mode of operation [unusual to change]')
def publish(zip, debug, mode):
    region = 'us-east-1' # always publish to us-east-1
    fp_common = FPCommon(region, debug, 'prod', mode)

    # read in conf
    conf = open('./faaspack_conf.yml', 'r')

    # parse in yaml
    confDict = yaml.load(conf)
    fp_common.debug('confDict %s' % confDict)

    name = confDict['name']
    version = confDict['version']

    # split name into scope and name
    name, scope = fp_common.fp_name_split(name)

    # check if version of FaaSPack exists
    # check FaaSPack for 'name' and 'version' exists and error if so
    exists = fp_common.fp_check_exists(name, version, scope)
    if(exists):
        fp_common.error("FaasPack - name: %(name)s, version: %(version)s already exists. Change to different version to publish." % locals(), True)
    else:
        # read faaspack.conf from current dir
        fp_common.info("Pubishing FaaSPack - name: %(name)s, version: %(version)s" % locals())

    # otherwise, upload zip & conf
    zipfile = open(zip, 'r')
    conf = open('./faaspack_conf.yml', 'r')
    fp_common.fp_upload_conf(conf, name, version, scope)
    fp_common.fp_upload_zip(zipfile, name, version, scope)

fp.add_command(install)
fp.add_command(update)
fp.add_command(configure)
# fp.add_command(uninstall)
fp.add_command(publish)

def sanitised_input(prompt, defaultVal=None, type_=None, min_=None, max_=None, range_=None):
    if min_ is not None and max_ is not None and max_ < min_:
        raise ValueError("min_ must be less than or equal to max_.")
    while True:
        ui = click.prompt(prompt, default=defaultVal)
        if type_ is not None:
            try:
                ui = type_(ui)
            except ValueError:
                print("Input type must be {0}.".format(type_.__name__))
                continue
        if max_ is not None and ui > max_:
            print("Input must be less than or equal to {0}.".format(max_))
        elif min_ is not None and ui < min_:
            print("Input must be greater than or equal to {0}.".format(min_))
        elif range_ is not None and ui not in range_:
            if isinstance(range_, range):
                template = "Input must be between {0.start} and {0.stop}."
                print(template.format(range_))
            else:
                template = "Input must be {0}."
                if len(range_) == 1:
                    print(template.format(*range_))
                else:
                    print(template.format(" or ".join((", ".join(map(str,
                                                                     range_[:-1])),
                                                       str(range_[-1])))))
        else:
            return ui

# if __name__ == '__main__':
#     fp()
    # fire.Fire()
