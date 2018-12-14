#! -*- coding: utf-8 -*-

# Description    Flame Manage class
##
# Authors:       Manuel Pastor (manuel.pastor@upf.edu)
##
# Copyright 2018 Manuel Pastor
##
# This file is part of Flame
##
# Flame is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 3.
##
# Flame is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
##
# You should have received a copy of the GNU General Public License
# along with Flame. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import shutil
import tarfile
import json
import pickle
import pathlib

from flame.util import utils, get_logger

LOG = get_logger(__name__)


def set_model_repository(path=None):
    """
    Set the model repository path.
    This is the dir where flame is going to create and load models
    """
    utils.set_model_repository(path)
    LOG.info(f'Model repository updated to {path}')


def action_new(model):
    '''
    Create a new model tree, using the given name.
    This creates the development version "dev",
    copying inside default child classes
    '''

    if not model:
        return False, 'empty model label'

    # Model directory with /dev (default) level
    ndir = pathlib.Path(utils.model_tree_path(model)) / 'dev'

    # check if there is already a tree for this endpoint
    if ndir.exists():
        LOG.warning(f'Endpoint {model} already exists')
        return False, 'This endpoint already exists'

    ndir.mkdir(parents=True)
    LOG.debug(f'{ndir} created')

    # Copy classes skeletons to ndir
    wkd = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
    children_names = ['apply', 'idata', 'odata', 'learn']

    for cname in children_names:
        filename = cname + '_child.py'
        src_path = wkd / 'children' / filename
        dst_path = ndir / filename
        shutil.copy(src_path, dst_path)

    LOG.debug(f'copied class skeletons from {src_path} to {dst_path}')
    # copy parameter yml file
    params_path = wkd / 'children/parameters.yaml'
    shutil.copy(params_path, ndir)

    LOG.info(f'New endpoint {model} created')
    return True, 'new endpoint '+model+' created'


def action_kill(model):
    '''
    removes the model tree described by the argument
    '''

    if not model:
        return False, 'empty model label'

    ndir = utils.model_tree_path(model)

    if not os.path.isdir(ndir):
        LOG.error(f'Model {model} not found')
        return False, 'model not found'

    shutil.rmtree(ndir, ignore_errors=True)

    LOG.info(f'Model {model} removed')
    return True, 'model '+model+' removed'


def action_publish(model):
    '''
    clone the development "dev" version as a new model version,
     assigning a sequential version number
    '''

    if not model:
        return False, 'empty model label'

    bdir = utils.model_tree_path(model)

    if not os.path.isdir(bdir):
        LOG.error(f'Model {model} not found')
        return False, 'model not found'

    # gets version number
    v = [int(x[-6:]) for x in os.listdir(bdir) if x.startswith("ver")]

    if not v:
        max_version = 0
    else:
        max_version = max(v)

    new_dir = bdir+'/ver%0.6d' % (max_version+1)

    if os.path.isdir(new_dir):
        LOG.error(f'Versin {v} of model {model} not found')
        return False, 'version already exists'

    src_path = bdir+'/dev'
    shutil.copytree(src_path, new_dir)
    LOG.info(f'New model version created from {src_path} to {new_dir}')
    return True, 'development version published as version '+str(max_version+1)


def action_remove(model, version):
    '''
    Remove the version indicated as argument from the model tree indicated
    as argument
    '''

    if not model:
        LOG.error('empty model label')
        return False, 'empty model label'

    if version == 0:
        LOG.error('development version cannot be removed')
        return False, 'development version cannot be removed'

    rdir = utils.model_path(model, version)
    if not os.path.isdir(rdir):
        LOG.error('version {} not found')
        return False, 'version not found'

    shutil.rmtree(rdir, ignore_errors=True)
    LOG.info(f'version {version} of model {model} has removed')
    return True, 'version '+str(version)+' of model '+model+' removed'


def action_list(model):
    '''
    Lists available models (if no argument is provided)
     and model versions (if "model" is provided as argument)
    '''

    # TODO: if no argument is provided, also list all models
    if not model:
        rdir = utils.model_repository_path()

        num_models = 0
        models = []
        print(' Models found in repository:')
        for x in os.listdir(rdir):
            num_models += 1
            models.append(x)
            print('\t- ', x)
        LOG.debug(f'Retrieved list of models from {rdir}')
        return True, ''

    bdir = utils.model_tree_path(model)

    num_versions = 0
    for x in os.listdir(bdir):
        if x.startswith("ver"):

            num_versions += 1
            print(model, ':', x)

    LOG.info(f'model {model} has {num_versions} published versions')
    return True, 'model '+model+' has '+str(num_versions)+' published versions'


def action_import(model):
    '''
    Creates a new model tree from a tarbal file with the name "model.tgz"
    '''

    if not model:
        return False, 'empty model label'

    # convert model to endpoint string
    base_model = os.path.basename(model)
    endpoint = os.path.splitext(base_model)[0]
    ext = os.path.splitext(base_model)[1]

    bdir = utils.model_tree_path(endpoint)

    if os.path.isdir(bdir):
        LOG.error(f'Endpoint already exists: {model}')
        return False, 'endpoint already exists'

    if ext != '.tgz':
        importfile = os.path.abspath(model+'.tgz')
    else:
        importfile = model

    LOG.info('importing {}'.format(importfile))

    if not os.path.isfile(importfile):
        LOG.info('importing package {} not found'.format(importfile))
        return False, 'importing package '+importfile+' not found'

    try:
        os.mkdir(bdir)
    except Exception as e:
        LOG.error(f'error creating directory {bdir}: {e}')
        raise e
        # return False, 'error creating directory '+bdir

    with tarfile.open(importfile, 'r:gz') as tar:
        tar.extractall(bdir)
    LOG.info('Endpoint {} imported OK'.format(endpoint))
    return True, 'endpoint '+endpoint+' imported OK'


def action_export(model):
    '''
    Exports the whole model tree indicated in the argument as a single
    tarball file with the same name.
    '''

    if not model:
        return False, 'empty model label'

    current_path = os.getcwd()
    exportfile = current_path+'/'+model+'.tgz'

    bdir = utils.model_tree_path(model)

    if not os.path.isdir(bdir):
        LOG.error('Unable to export, model directory not found')
        return False, 'endpoint directory not found'

    os.chdir(bdir)

    itemend = os.listdir()
    itemend.sort()

    with tarfile.open(exportfile, 'w:gz') as tar:
        for iversion in itemend:
            if not os.path.isdir(iversion):
                continue
            tar.add(iversion)

    os.chdir(current_path)
    LOG.info('Model exported as {}.tgz'.format(model))
    return True, 'endpoint '+model+' exported as '+model+'.tgz'


# TODO: implement refactoring, starting with simple methods
def action_refactoring(file):
    '''
    NOT IMPLEMENTED,
    call to import externally generated models (eg. in KNIME or R)
    '''

    print('refactoring')

    return True, 'OK'


def action_dir():
    '''
    Returns a JSON with the list of models and versions
    '''
    # get de model repo path
    models_path = pathlib.Path(utils.model_repository_path())

    # get directories in model repo path
    dirs = [x for x in models_path.iterdir() if x.is_dir()]

    # if dir contains dev/ -> is model (NAIVE APPROACH)
    # get last dir name [-1]: model name
    model_dirs = [d.parts[-1] for d in dirs if list(d.glob('dev'))]

    results = []
    for imodel in model_dirs:

        # versions = ['dev']
        versions = [{'text': 'dev'}]

        for iversion in os.listdir(utils.model_tree_path(imodel)):
            if iversion.startswith('ver'):
                # versions.append (iversion)
                versions.append({'text': iversion})

        # results.append ((imodel,versions))
        results.append({'text': imodel, 'nodes': versions})

    return True, json.dumps(results)

    # print(json.dumps(results))


def action_info(model, version=None, output='text'):
    '''
    Returns a text or JSON with results info for a given model and version
    '''

    if model is None:
        return False, 'empty model label'

    if version is None:
        return False, 'no version provided'

    rdir = utils.model_path(model, version)
    if not os.path.isfile(os.path.join(rdir, 'info.pkl')):
        return False, 'info not found'

    with open(os.path.join(rdir, 'info.pkl'), 'rb') as handle:
        results = pickle.load(handle)
        results += pickle.load(handle)

    if output == 'text':
        for val in results:
            if len(val) < 3:
                print(val)
            else:
                print(val[0], ' (', val[1], ') : ', val[2])
        return True, 'model informed OK'

    new_results = []

    # results must be checked to avoid numpy elements not JSON serializable
    for i in results:
        if 'numpy.int64' in str(type(i[2])):
            try:
                v = int(i[2])
            except Exception as e:
                LOG.error(e)
                v = None
            new_results.append((i[0], i[1], v))
        elif 'numpy.float64' in str(type(i[2])):
            try:
                v = float(i[2])
            except Exception as e:
                LOG.error(e)
                v = None
            new_results.append((i[0], i[1], v))
        else:
            new_results.append(i)

    return True, json.dumps(new_results)
