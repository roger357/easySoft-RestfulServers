from flask import Flask, request
from flask_cors import CORS
from flask_restful import Resource, Api
from collections import OrderedDict
from flask.ext.jsonpify import jsonify
from git import Repo
from modificationtype import DiffType
from searchtype import SearchType
from line import LineRailCreator
import re
from datetime import *
import logging

# WebService Intance
app = Flask(__name__)
CORS(app)
app.config.from_object('gitwebconf.Config')
'''
This way is for load Configuration file fron OS Shell
app.config.from_envvar('YOURAPPLICATION_SETTINGS')
'''


# Ruta al repositorio
#repo = Repo('C:/Users/anonimous/Documents/branch/Acsel-e')
#repo = Repo('C:/Users/anonimous/Documents/Proyectos/IDEOS')
repo = Repo('/home/roger/Documentos/repos/IDEOS')
logging.getLogger().setLevel(logging.INFO)


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/commitviewer/allbranchs/')
def list_all_branchs():
    branchs_list = []
    # for k, v in OrderedDict(sorted(branchs.items(), key=lambda x: x[1], reverse=True)).items():
    for branch in repo.references:
        try:
            if branch.tracking_branch() is None:
                branchs_list.append({
                    'branchName': branch.remote_head,
                    'lastCommit': branch.commit.hexsha})
        except AttributeError:
            app.logger.info('No se procesa el branch ' + str(branch))
    return jsonify(branchs_list)


@app.route('/commitviewer/branchs')
def get_branch_by_name():
    search_term = request.args.get('searchTerm')
    branchs_list = []
    # Este condicional evita que realice busquedas con estring vacios.
    if search_term:
        for branch in repo.references:
            try:
                if branch.tracking_branch() is None:
                    if search_term in branch.remote_head:
                        branchs_list.append({
                            'branchName': branch.remote_head,
                            'lastCommit': branch.commit.hexsha})
            except AttributeError:
                app.logger.info('No se procesa el branch ' + str(branch))
    return jsonify(branchs_list)

@app.route('/commitviewer/toplist/')
def list_top_branchs():
    branchs = get_top_branchs()
    branchs_list = []
    count = 0
    for k, v in OrderedDict(sorted(branchs.items(), key=lambda x: x[1], reverse=True)).items():
        branchs_list.append({'branchName': k.remote_head,
                             'lastCommit': k.commit.hexsha})
        count += 1
        if count == 5:
            break
    return jsonify(branchs_list)


@app.route('/commitviewer/branch/commits')
def list_branch_commits():
    """
    Consult and Return commit for especific branch.

    :return:            Commit Objects that was requested
    """
    branch_name = request.args.get('branchName')
    commits = request.args.get('commits')
    searchBy = request.args.get('searchBy')
    searchParam = request.args.get('searchParam')
    commitlist = []
    git_pull()
    branch = 'origin/{0}'.format(branch_name)
    for commit in repo.iter_commits(branch, max_count=commits):
        if searchBy :
            search = int(searchBy)
            if search == SearchType.AUTHOR.value and searchParam.upper() not in commit.author.name.upper():
                continue
            elif search == SearchType.MESSAGE.value and searchParam.upper() not in commit.message.upper():
                continue
            elif search == SearchType.SHA.value and searchParam.upper() != commit.hexsha.upper():
                continue
            elif search == SearchType.DATE.value:
                commit_time = commit.committed_datetime
                commit_date = '{0:04d}-{1:02d}-{2:02d}'.format(commit_time.year, commit_time.month,commit_time.day)
                dates = searchParam.split("*")
                dateFrom = datetime.strptime(dates[0], '%Y-%m-%d')
                dateTo = datetime.strptime(dates[1], '%Y-%m-%d')
                dateCommit = datetime.strptime(commit_date, '%Y-%m-%d')
                if not (dateFrom <= dateCommit <= dateTo):
                    continue

        commitlist.append(get_commit_details(commit))

    # result = {'Branch': branch_name, 'Commits': commitlist}
    result = {'Commits': commitlist}
    return jsonify(commitlist)


@app.route('/commitviewer/commitdetail')
def get_commit_Detail():
    sha = request.args.get('sha')
    short_message = int(request.args.get('shortMessage'))
    commit = repo.commit(sha)
    return jsonify(get_commit_details(commit, short_message == 1))

# repo.git.diff('2507ffaf3773f86646dd948cde7f2bfbeac31bc5','5c784ddff848b660cd665f2fab635805d2940921','Test/static/web/bootstrap/css/bootstrap.css')
@app.route('/commitviewer/commitdetail/files/diffs')
def get_commit_files():
    change_types = ['A', 'D', 'R', 'M']
    sha = request.args.get('sha')
    commit = repo.commit(sha)
    mod_files_diff = []
    for change_type in change_types:
        diff_list = list(commit.diff(commit.parents[0], create_patch=True).iter_change_type(change_type))
        for diff in diff_list:
            modified_file = {}
            if change_type == 'A':
                file_path = diff.b_path
            else:
                file_path = diff.a_path

            modified_file['filePath'] = file_path
            modified_file['modificationType'] = change_type
            # Cambios realizados en el archivo
            file_commits = list(repo.iter_commits(paths=file_path))
            diffs = repo.git.diff(file_commits[len(file_commits)-1], sha, file_path)
            modified_file['fileDiffs'] = diffs

            mod_files_diff.append(modified_file)
    return jsonify(mod_files_diff)


def get_diff_lines(group, diff):
    if not group:
        return {'modificationType': 0, 'lineContent': ''}
    # Pattern for Deleted Lines
    deleted_patt = re.compile(r'(-[0-9]*,[0-9]*)')
    # Pattern for Added
    added_patt = re.compile(r'(\+[0-9]*,[0-9]*)')
    # total_lines = deleted_patt.findall(group)[0].split(',')[1]
    deleted_lines = deleted_patt.findall(group)[0].split(',')[0]
    added_lines = added_patt.findall(group)[0].split(',')[0]
    if deleted_lines > added_lines:
        init_line = added_lines
    else:
        init_line = deleted_lines
        
    line_number = int(init_line[1:])
    modified_lines = []
    line_numbers_aux = []

    rail_creator = LineRailCreator(int(deleted_lines[1:]), int(init_line[1:]))
    for line in diff.split('\n'):
        line_content = line[1:]
        if line[0:1] == '+':
            modfication_type = DiffType.ADD.value
            lines = rail_creator.generate_linediff_add()
        elif line[0:1] == '-':
            modfication_type = DiffType.DEL.value
            line_numbers_aux.append(line_number)
            lines = rail_creator.generate_linediff_del()
        else:
            modfication_type = DiffType.NONE.value
            lines = rail_creator.generate_linediff_untouch()

        values = {'modificationType': modfication_type, 'lineContent': line_content}
        values.update(lines)
        modified_lines.append(values)
    return modified_lines



@app.route('/commitviewer/branchcount/')
def get_branch_count():
    count = 0
    for branch in repo.references:
        try:
            if branch.tracking_branch() is None:
                count += 1
        except AttributeError:
            app.logger.info('No se procesa el branch ' + str(branch))
    return jsonify(count)


@app.route('/commitviewer/commitscount')
def get_commit_count():
    count = 0
    branch = 'origin/{0}'.format(request.args.get('branch'))
    return jsonify(len(list(repo.iter_commits(branch))))


@app.route('/commitviewer/branch/commitsperpage')
def get_commits_per_page():
    branch_name = request.args.get('branchName')
    page = int(request.args.get('page'))
    itemPerPage = int(request.args.get('itemPerPage'))
    maxPagesView = int(request.args.get('maxPagesView'))
    searchBy = int(request.args.get('searchBy'))
    searchParam = request.args.get('searchParam')
    commitlist = []
    git_pull()
    commitsquantity = itemPerPage * maxPagesView
    if page == 1:
        infLimit = 0
    else:
        infLimit = ((itemPerPage * page) - itemPerPage) + 1
    branch = 'origin/{0}'.format(branch_name)
    for commit in list(repo.iter_commits(branch))[infLimit: infLimit + (commitsquantity)]:
        if searchBy :
            if searchBy == SearchType.AUTHOR.value and searchParam.upper() not in commit.author.name.upper():
                continue
            elif searchBy == SearchType.MESSAGE.value and searchParam.upper() not in commit.message.upper():
                continue
            elif searchBy == SearchType.SHA.value and searchParam.upper() != commit.hexsha.upper():
                continue
            elif searchBy == SearchType.DATE.value:
                commit_time = commit.committed_datetime
                commit_date = '{0:04d}-{1:02d}-{2:02d}'.format(commit_time.year, commit_time.month,commit_time.day)
                dates = searchParam.split(str="*")
                dateFrom = datetime.date.strptime(dates[0], '%Y-%m-%d')
                dateTo = datetime.date.strptime(dates[1], '%Y-%m-%d')
                if not (dateFrom <= commit_date <= dateTo):
                    continue
        commitlist.append(get_commit_details(commit))
    print(infLimit)
    print(infLimit + (commitsquantity))
    return jsonify(commitlist)


# Este paginador sera mas util con los commits
@app.route('/commitviewer/branchpage')
def get_branchs_per_page():
    items_p_page = int(request.args.get('itemsPerPage'))
    page_number = int(request.args.get('pageNumber'))
    ls = page_number * items_p_page
    if page_number == 1:
        li = 0
    else:
        li = ls - items_p_page

    branchs_list = []
    for branch in repo.references:
        try:
            if branch.tracking_branch() is None:
                branch_name = 'origin/{0}'.format(branch.remote_head)
                commit = iter(repo.iter_commits(branch_name, max_count=1)).__next__()  # Ultimo commit
                branchs_list.append({'branchName': branch_name[branch_name.find('/')+1:],
                                     'lastCommit': get_commit_details(commit)})
        except AttributeError:
            app.logger.info('No se procesa el branch ' + str(branch))
    return jsonify(branchs_list[li:ls])


# @app.route('/commitviewer/commitdetail/fileblame')
# def get_commit_file_name_blame():
#     sha = request.args.get('sha')
#     file_path = request.args.get('filePath')
#     for blameEntry in repo.blame_incremental(sha, file_path):
#         for n in blameEntry.linenos:



def git_pull():
    app.logger.info('Doing Git Pull')
    app.logger.info(repo.git.pull())


def get_commit_modified_files(commit, parent):
    return len(commit.diff(parent))


def get_commit_details(commit, short_message=True):
    commit_time = commit.committed_datetime
    date = '{0:04d}/{1:02d}/{2:02d} {3:02d}:{4:02d}:{5:02d}'.format(commit_time.year, commit_time.month,
                                                                    commit_time.day, commit_time.hour,
                                                                    commit_time.minute, commit_time.second)
    if short_message:
        commitmsg = commit.message[0:commit.message.find('\n')]
    else:
        commitmsg = commit.message.replace('\n', '<br>')

    commit_data = {'commitDate': date,
                   'sha': commit.hexsha,
                   'sha8': commit.hexsha[0:8],
                   'message': commitmsg,
                   'author': commit.author.name,
                   'modifiedFiles': get_commit_modified_files(commit, commit.parents[0])
                   if len(commit.parents) > 0 else 0}
    return commit_data


def get_top_branchs():
    git_pull()
    today = date.today()  # - datetime.timedelta(days=200) Ultimos 200 dias
    branchs = {}
    for branch in repo.references:
        count = 0
        try:
            if branch.tracking_branch() is None:
                branch_name = 'origin/{0}'.format(branch.remote_head)
                for commit in repo.iter_commits(branch_name, max_count=100):
                    if (today - timedelta(days=30)) <= commit.committed_datetime.date() <= today:
                        count += 1
                if count > 0:
                    branchs[branch] = count
        except AttributeError:
            app.logger.info('No se procesa el branch ' + str(branch))
    return branchs


def get_all_branchs():
    git_pull()
    today = date.today()  # - datetime.timedelta(days=2)
    branchs = {}
    for branch in repo.references:
        count = 0
        try:
            if branch.tracking_branch() is None:
                branch_name = 'origin/{0}'.format(branch.remote_head)
                for commit in repo.iter_commits(branch_name, max_count=100):
                    #if commit.committed_datetime.date() == today:
                    count += 1
                if count > 0:
                    branchs[branch_name] = count
        except AttributeError:
            app.logger.info('No se procesa el branch ' + str(branch))
    return branchs


if __name__ == '__main__':
    app.run(port=5002)
