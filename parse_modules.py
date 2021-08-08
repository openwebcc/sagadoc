#!/usr/bin/python
#
# explore SAGA tools
#

import os

if os.name == 'nt': # Windows
    if os.getenv('SAGA_PATH') is None:
        os.environ['SAGA_PATH'] = 'C:/develop/saga'                                     # SAGA installation path
    os.add_dll_directory(os.environ['SAGA_PATH'])
    os.environ['SAGA_TLB'  ] = os.environ['SAGA_PATH'] + os.sep + 'tools'               # SAGA tool libraries path
    os.environ['PATH'      ] = os.environ['SAGA_PATH'] + os.sep +    ';' + os.environ['PATH']
    os.environ['PATH'      ] = os.environ['SAGA_PATH'] + os.sep + 'dll;' + os.environ['PATH']
    
import re
import argparse
import json as simplejson
import subprocess
import saga_api
import shutil

from string import Template

HTML_PATH = './html'
TPL_TERMS = {}

class Util():
    """ utility functions """
    def __init__(self):
        """ initialize utility class """
        pass

    def get_saga_version(self):
        """ return version number of current SAGA-API """
        return saga_api.SAGA_API_Get_Version().split(' ')[-1]

    def read_template(self, fpath=None):
        """ safely read the given template file into a string """
        s = ""
        if os.path.exists(fpath):
            with open(fpath) as tpl:
                s = tpl.read()
        return s

    def cstr_2_str(self, value=None):
        """ return SWIG c_str value as Python str """
        if value:
            if type(value.c_str()) == str:
                return value.c_str()
            else:
                print (type(value.c_str()))
                return value.c_str().encode('utf8')
        else:
            return ''

    def toolreferences_2_str(self, value=None):
        """ convert tool references (CSG_Strings array) to a HTML list and return Python str """
        if value.Get_Count() > 0:
            s = "<hr><h3><em>References</em></h3><ul>"
            for i in range (0, value.Get_Count()):
                s += ("<li>" + self.cstr_2_str(value.Get_String(i)) + "</li>")
            s += "</ul><hr>"
        else:
            s = ""
        return s

    def get_wikilinks(self):
        """ resolve known WIKI entries """
        links = {}
        o = open('wikilinks.txt')
        for line in o.readlines():
            row = line.rstrip().split('\t')
            if row[0] == 'TOOL' or len(row) != 2:
                continue
            links[u"%s" % row[0]] = row[1]
        o.close()
        return links

    def lib_name_from_so(self, name=None):
        """ strip optional path info, lib prefix and .so extenstion
            /usr/local/lib/saga/contrib_a_perego.so results in contrib_a_perego
            return libname as UTF-8 as SWIG might otherwise fail with TypeError: bad argument type for built-in operation
        """
        if os.name == 'nt':
            return '%s' % name.split('\\')[-1][:-4]
        else:
            return '%s' % name.split('/')[-1][3:][:-3]

    def parse_parameters(self, tool_obj=None):
        """ parse SAGA parameters object and create python dictionary
            see http://www.saga-gis.org/saga_api_doc/html/module_8cpp_source.html#l00928 (CSG_Module::Get_Summary)
        """
        params = {}
        for n in range(0, tool_obj.Get_Parameters().Get_Count()):
            param = tool_obj.Get_Parameters().Get_Parameter(n)
            param_type = ""
            if param.is_Input():
                param_type = "Input"
            elif param.is_Output():
                param_type = "Output"
            elif param.is_Option() and param.Get_Type() != 14:  #PARAMETER_TYPE_Grid_System
                param_type = "Options"
            else:
                continue

            # make sure dictionary key is present
            if not param_type in params:
                params[param_type] = []

            # see dir(tool_obj.Get_Parameters().Get_Parameter(0))
            params[param_type].append({
                'Get_Name' : param.Get_Name(),
                'Get_Identifier' : param.Get_Identifier(),
                'Get_Type' : param.Get_Type(),
                'Get_Type_Identifier' : self.cstr_2_str(param.Get_Type_Identifier()),
                'Get_Type_Name' : self.cstr_2_str(param.Get_Type_Name()),
                'Get_Description' : param.Get_Description(),
                'Get_Description_2' : self.cstr_2_str(param.Get_Description(2)),  #PARAMETER_DESCRIPTION_TYPE
                'Get_Description_8' : self.cstr_2_str(param.Get_Description(8)),  #PARAMETER_DESCRIPTION_PROPERTIES
                'is_Information' : param.is_Information(),
                'is_Input' : param.is_Input(),
                'is_Option' : param.is_Option(),
                'is_Optional' : param.is_Optional(),
                'is_Output' : param.is_Output(),
            })
        return params

    def add_brs(self, s=None):
        """ replace \n with <br> in string """
        if s:
            return re.sub(r'\n', '<br>', s)
        else:
            return s

    def as_json(self, obj=None):
        """ return JSON string from object escaping "<" """
        json = simplejson.dumps(obj, indent=True, sort_keys=True)
        json = re.sub("<","&lt;",json)
        return "<h3>Debug JSON</h3><pre class='usage'>%s</pre>" % json

# parse commandline
parser = argparse.ArgumentParser(description='import opendata for ooe application.')
default_libpath = '/usr/local/lib/saga'
if os.name == 'nt':
    default_libpath = os.environ['SAGA_TLB']
parser.add_argument('--libpath', dest='libpath', default=default_libpath, help='path to shared object library files')
parser.add_argument('--lib', dest='lib', help='parse given library only')
parser.add_argument('--tool', dest='tool', help='parse given tool only')
parser.add_argument('--skip', dest='skip', help='skip libraries from beeing processed (e.g --skip imagery_classification,imagery_svm,geostatistics_kriging,ihacres)')
parser.add_argument('--debugjson', dest='debugjson', action='store_true', help='add JSON dictionaries for debugging to HTML pages')
args = parser.parse_args()

has_errors = False
has_debug = False
error_log = open('error_log.txt','w')
debug_log = open('debug_log.txt','w')

libraries = {}
a2z = {}

# initialize utility class
util = Util()

# define wikilinks
wikilinks = util.get_wikilinks()

# make sure target directory with version number for docs exists
HTML_PATH = "%s/%s" % (HTML_PATH,util.get_saga_version())
if not os.path.exists(HTML_PATH):
    os.mkdir(HTML_PATH)

# add template term for version number
TPL_TERMS['VERSION'] = util.get_saga_version()

# add empty JSON debug template term
TPL_TERMS['Debug_JSON'] = ''

for fname in os.listdir(args.libpath):
    # parse optional commandline options
    if args.lib and util.lib_name_from_so(fname) != args.lib:
        continue
    if args.tool and not re.match(r'^%s_[0-9]+$' % util.lib_name_from_so(fname), args.tool):
        continue
        
    if os.name == 'nt':
        if fname[-4:] != '.dll':
            continue
    else:
        if fname[-3:] != '.so':
            continue

    print('parsing {}/{} ...'.format(args.libpath,fname))

    # load library
    if args.skip and util.lib_name_from_so(fname) in args.skip.split(','):
        print('SKIPPING library {} as requested ...'.format(util.lib_name_from_so(fname)))
        continue
    else:
        saga_api.SG_Get_Tool_Library_Manager().Add_Library('%s/%s' % (args.libpath,fname))

    # define shortcut to library object
    lib_obj = saga_api.SG_Get_Tool_Library_Manager().Get_Library(0)

    # define unique name for library
    lib_name = ''
    if os.name == 'nt':
        lib_name = util.lib_name_from_so('%s' % fname)
    else:
        lib_name = util.lib_name_from_so('%s/%s' % (args.libpath,fname))

    # define library title as we will use it more than once
    lib_title = '%s - %s' % (util.cstr_2_str(lib_obj.Get_Category()),util.cstr_2_str(lib_obj.Get_Name()) )

    # remember library details - see dir(lib_obj)
    libraries[lib_title] = {
        'Get_Author' : util.cstr_2_str(lib_obj.Get_Author()),
        'Get_Count' : lib_obj.Get_Count(),
        'Get_Description' : util.cstr_2_str(lib_obj.Get_Description()),
        'Get_File_Name' : util.cstr_2_str(lib_obj.Get_File_Name()),
        'Get_Library_Name' : util.cstr_2_str(lib_obj.Get_Library_Name()),
        'Get_Menu' : util.cstr_2_str(lib_obj.Get_Menu()),
        'Get_Name' : util.cstr_2_str(lib_obj.Get_Name()),
        'Get_Version' : util.cstr_2_str(lib_obj.Get_Version()),
        'is_Valid' : lib_obj.is_Valid(),
        'doc_Links' : {},    # will be filled while parsing tools
    }

    # resolve WIKI link if any
    if lib_name in wikilinks:
        libraries[lib_title]['WIKI_Link'] = wikilinks[lib_name]
    else:
        libraries[lib_title]['WIKI_Link'] = None

    # loop through library tools and collect details
    for i in range(0,libraries[lib_title]['Get_Count']):
        # load tool
        tool_obj = lib_obj.Get_Tool(i)
        tool_obj_id = tool_obj.Get_ID()

        # make sure that tool is valid
        if not 'Get_Name' in dir(tool_obj):
            continue

        # skip tool if needed
        if args.tool and "%s_%s" % (lib_name, tool_obj_id.c_str()) != args.tool:
            continue

        # remember tool details - see dir(tool_obj)
        #print "DEBUG: %s_%s" % (lib_name, tool_obj_id.c_str())
        details = {
            'Get_Author' : util.cstr_2_str(tool_obj.Get_Author()),
            'Get_Description' : util.cstr_2_str(tool_obj.Get_Description()),
            'Get_References' : util.toolreferences_2_str(tool_obj.Get_References()),
            'Get_ID' : tool_obj.Get_ID(),
            'Get_Icon' : tool_obj.Get_Icon(),
            'Get_MenuPath' : util.cstr_2_str(tool_obj.Get_MenuPath()),
            'Get_Name' : util.cstr_2_str(tool_obj.Get_Name()),
            'Get_Parameters' : util.parse_parameters(tool_obj),
            'Get_Parameters_Count' : tool_obj.Get_Parameters_Count(),
            'Get_Type' : tool_obj.Get_Type(),
            'is_Grid' : tool_obj.is_Grid(),
            'is_Interactive' : tool_obj.is_Interactive(),
            'needs_GUI' : False if not hasattr(tool_obj,'needs_GUI') else tool_obj.needs_GUI()    # introduced in https://sourceforge.net/p/saga-gis/code-0/2111/
        }

        # replace \n  with <br> in tool description
        details['Get_Description_HTML'] = util.add_brs(details['Get_Description'])

        # resolve full path for menu entry
        details['Full_Menu_Path'] = libraries[lib_title]['Get_Menu']
        if details['Get_MenuPath'] != "":
            if  details['Get_MenuPath'][:2] == 'R:':
                details['Full_Menu_Path'] += "|%s" % details['Get_MenuPath'][2:]
            elif  details['Get_MenuPath'][:2] == 'A:':
                details['Full_Menu_Path'] = details['Get_MenuPath'][2:]
            else:
                details['Full_Menu_Path'] += "|%s" % details['Get_MenuPath']    # same as R: according to olaf

        # resolve WIKI link if any
        if ("%s_%s" % (lib_name,i)) in wikilinks:
            details['WIKI_Link'] = wikilinks["%s_%s" % (lib_name,tool_obj_id.c_str())]
        else:
            details['WIKI_Link'] = None

        # define tool title that will be used in index and a2z pages consisting of tool name and interactive switch
        tool_title = "%s%s" % (
            util.cstr_2_str(tool_obj.Get_Name()),
            ' (interactive)' if details['is_Interactive'] else ''
        )

        # remember links to tool docs by title
        libraries[lib_title]['doc_Links'][tool_title] = '%s_%s.html' % (lib_name, tool_obj_id.c_str())

        # fill a2z index, use list approach to ensure that duplicate tool names in different libraries don't get lost
        if not tool_title in a2z:
            a2z[tool_title] = []
        a2z[tool_title].append('<tr><td><a href="%s">%s</a></td><td class="menuPath">%s</td></tr>' % (
            '%s_%s.html' % (lib_name, tool_obj_id.c_str()),
            tool_title,
            details['Full_Menu_Path']
        ))

        # unload tool
        tool_obj.Destroy()

        # create tool page
        TPL_TERMS['Get_Name'] = tool_title
        TPL_TERMS['Get_Author'] = details['Get_Author']
        TPL_TERMS['Get_ID'] = details['Get_ID']
        TPL_TERMS['Get_Description'] = details['Get_Description']
        TPL_TERMS['Get_Description_HTML'] = details['Get_Description_HTML']
        TPL_TERMS['Get_References'] = details['Get_References']

        TPL_TERMS['Full_Menu_Path'] = details['Full_Menu_Path']
        if args.debugjson:
            TPL_TERMS['Debug_JSON'] = util.as_json(details)

        # add link to WIKI if any
        if details['WIKI_Link']:
            TPL_TERMS['WIKI_Link'] = '<li>WIKI: <a href="%s">%s</a></li>' % (
                details['WIKI_Link'],
                details['WIKI_Link']
            )
        else:
            TPL_TERMS['WIKI_Link'] = ''

        # define parameters
        has_optional = False
        for section in ["Input","Output","Options"]:
            if section in details['Get_Parameters']:
                rows = []
                section_column = None
                for param in details['Get_Parameters'][section]:
                    # mark optional entries
                    is_optional = ""
                    if param['is_Optional']:
                        is_optional = " (*)"
                        has_optional = True

                    # add section in first column
                    if not section_column:
                        section_column = '<td rowspan="%s" class="labelSection">%s</td>' % (
                            len(details['Get_Parameters'][section]),
                            section
                        )
                    else:
                        section_column = ' '

                    rows.append('<tr>%s<td>%s%s</td><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td></tr>\n' % (
                        section_column,
                        param['Get_Name'],
                        is_optional,
                        (param['Get_Description_2']) or '-',
                        (param['Get_Identifier']) or '-',
                        (param['Get_Description']) or '-',
                        (util.add_brs(param['Get_Description_8'])) or '-'
                    ))
                TPL_TERMS['PARAMS_%s' % section] = '\n'.join(rows)
            else:
                TPL_TERMS['PARAMS_%s' % section] = ''

        # add footnote if optional parameters
        TPL_TERMS['HINT_Optional'] = '%s' % (
            '<tr><td colspan="6">(*) optional</td></tr>' if has_optional else ''
        )

        # list tools with clashing is_Interactive and needs_GUI switches
        if not details['is_Interactive'] == details['needs_GUI']:
            debug_log.write("DEBUG: %s has is_Interactive=%s and needs_GUI=%s\n" % (
                tool_title,details['is_Interactive'],details['needs_GUI']
            ))
            has_debug = True

        # resolve saga_cmd usage for tools that do not need the GUI or are non-interactive
        if not details['is_Interactive']:
            proc = subprocess.Popen(['saga_cmd', lib_name, tool_obj_id.c_str()], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            out, err = proc.communicate()
            if err:
                if details['needs_GUI']:
                    # set GUI hint as cmd usage
                    TPL_TERMS['Saga_Cmd'] = re.sub('Error: ','',err)
                else:
                    print('ERROR: saga_cmd {} {} '.format(lib_name, tool_obj_id.c_str()))
                    error_log.write("ERROR: saga_cmd %s %s\n" % (lib_name,tool_obj_id.c_str()))
                    error_log.write("       %s\n" % err)
                    TPL_TERMS['Saga_Cmd'] = "ERROR: %s" % err
            if out and not details['needs_GUI']:
                # extract tool usage
                usage = []
                collect_usage = False
                for line in out.split('\n'):
                    if line[:5] == "Usage":
                        collect_usage = True
                    if collect_usage:
                        # fix missing lib_name and lib number for saga_cmd help prior to 2.1.3
                        if not re.search('saga_cmd %s %s' % (lib_name,tool_obj_id.c_str()), line):
                            line = re.sub("saga_cmd", "saga_cmd %s %s" % (lib_name,tool_obj_id.c_str()), line)

                        # escape markup
                        line = re.sub("<","&lt;", line)

                        # mark command
                        line = re.sub('saga_cmd %s %s' % (lib_name,tool_obj_id.c_str()),'<strong>saga_cmd %s %s</strong>' % (lib_name,tool_obj_id.c_str()), line)

                        # append line
                        usage.append(line)

                if not usage:
                    error_log.write("WARNING: saga_cmd %s %s has no, or unknown usage string:\n%s\n\n" % (lib_name,tool_obj_id.c_str(),usage))
                    print('NOTICE: saga_cmd {} {} has no, or unknown usage string. Please check.'.format(lib_name, tool_obj_id.c_str()))
                TPL_TERMS['Saga_Cmd'] = "%s" % (
                    '\n'.join(usage)
                )
        else:
            TPL_TERMS['Saga_Cmd'] = 'this interactive tool can not be executed.'

        # add backlink
        TPL_TERMS['BACK_Link'] = "./%s.html" % lib_name
        TPL_TERMS['BACK_Text'] = lib_title

        # resolve tool template
        s = Template(util.read_template('./templates/tool.tpl'))
        o = open("%s/%s_%s.html" % (HTML_PATH,lib_name,tool_obj_id.c_str()), "wb")
        o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
        o.close()
        print('created {}/{}_{}.html'.format(HTML_PATH, lib_name, tool_obj_id.c_str()))

    # unload library
    saga_api.SG_Get_Tool_Library_Manager().Del_Library(0)

    # create index page for tools in library
    TPL_TERMS['Tool_Links'] = ''
    TPL_TERMS['Get_Name'] = libraries[lib_title]['Get_Name']
    TPL_TERMS['Get_Author'] = libraries[lib_title]['Get_Author']
    TPL_TERMS['Get_Version'] = libraries[lib_title]['Get_Version']
    TPL_TERMS['Get_File_Name'] = libraries[lib_title]['Get_File_Name']
    TPL_TERMS['Get_Menu'] = libraries[lib_title]['Get_Menu']
    TPL_TERMS['Get_Description'] = libraries[lib_title]['Get_Description']
    if args.debugjson:
        TPL_TERMS['Debug_JSON'] = util.as_json(libraries[lib_title])

    # add link to WIKI if any
    if libraries[lib_title]['WIKI_Link']:
        TPL_TERMS['WIKI_Link'] = '<li>WIKI: <a href="%s">%s</a></li>' % (
            libraries[lib_title]['WIKI_Link'],
            libraries[lib_title]['WIKI_Link']
        )
    else:
        TPL_TERMS['WIKI_Link'] = ''

    # set links to tool pages
    order = list(libraries[lib_title]['doc_Links'].keys())
    order.sort()
    for tool_name in order:
        TPL_TERMS['Tool_Links'] += "<li><a href='%s'>%s</a></li>" % (
            libraries[lib_title]['doc_Links'][tool_name],
            tool_name
        )

    # resolve library template
    s = Template(util.read_template('./templates/library.tpl'))
    o = open("%s/%s.html" % (HTML_PATH,lib_name), "wb")
    o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
    o.close()
    print('created {}/{}.html'.format(HTML_PATH, lib_name))

# create index page for libraries
TPL_TERMS['Library_Links'] = ''
if args.debugjson:
    TPL_TERMS['Debug_JSON'] = util.as_json(libraries)

# set links to library pages
order = list(libraries.keys())
order.sort()
for lib_name in order:
    TPL_TERMS['Library_Links'] += "<tr><td style='white-space: nowrap'><a href='%s'>%s</a></td><td>%s</td><td class='center'>%s</td></tr>" % (
        "%s.html" % util.lib_name_from_so(libraries[lib_name]['Get_File_Name']),
        lib_name,
        libraries[lib_name]['Get_Description'],
        len(libraries[lib_name]['doc_Links'].keys())
    )

# resolve startpage template
s = Template(util.read_template('./templates/index.tpl'))
o = open("%s/index.html" % (HTML_PATH), "wb")
o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
o.close()
print('created {}/index.html'.format(HTML_PATH))

# create a2z index page
TPL_TERMS['A2Z_Links'] = ''

order = list(a2z.keys())
order.sort()
for name in order:
    TPL_TERMS['A2Z_Links'] += "%s\n" % ('\n'.join(a2z[name]))

# resolve a2z template
s = Template(util.read_template('./templates/a2z.tpl'))
o = open("%s/a2z.html" % (HTML_PATH), "wb")
o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
o.close()
print('created {}/a2z.html'.format(HTML_PATH))

# copy lib/ and icons/ directories to html-path
print('\ncopying ./html/lib/ and ./html/icons/ directory to {} ...'.format(HTML_PATH))
for subdir in ('lib','icons'):
    shutil.rmtree("%s/%s" % (HTML_PATH,subdir), True)
    shutil.copytree("./html/%s" % subdir, "%s/%s" % (HTML_PATH,subdir))
    shutil.rmtree("%s/%s/.svn" % (HTML_PATH,subdir), True)

# finish error and debug messages
error_log.close()
debug_log.close()

if has_errors:
    print('\nlogged ERRORS to error_log.txt')
if has_debug:
    print('\nlogged DEBUG messages to debug_log.txt')

"""

saga_api.SG_Get_Tool_Library_Manager().Add_Library('/usr/local/lib/saga/libcontrib_a_perego.so')
tool_obj = saga_api.SG_Get_Tool_Library_Manager().Get_Tool('contrib_a_perego', 0)

"""
