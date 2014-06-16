#!/usr/bin/python
#
# explore SAGA modules
#

import os
import re
import argparse
import simplejson
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
            if type(value.c_str()) == unicode:
                return value.c_str()
            else:
                print type(value.c_str())
                return value.c_str().encode('utf8')
        else:
            return u''

    def get_wikilinks(self):
        """ resolve known WIKI entries """
        links = {}
        o = open('wikilinks.txt')
        for line in o.readlines():
            row = line.rstrip().split('\t')
            if row[0] == 'MODULE' or len(row) != 2:
                continue
            links[u"%s" % row[0]] = row[1]
        o.close()
        return links

    def lib_name_from_so(self, name=None):
        """ strip optional path info, lib prefix and .so extenstion
            /usr/local/lib/saga/contrib_a_perego.so results in contrib_a_perego
            return libname as UTF-8 as SWIG might otherwise fail with TypeError: bad argument type for built-in operation
        """
        return u'%s' % name.split('/')[-1][3:][:-3]

    def parse_parameters(self, mod_obj=None):
        """ parse SAGA parameters object and create python dictionary
            see http://www.saga-gis.org/saga_api_doc/html/module_8cpp_source.html#l00928 (CSG_Module::Get_Summary)
        """
        params = {}
        for n in range(0, mod_obj.Get_Parameters().Get_Count()):
            param = mod_obj.Get_Parameters().Get_Parameter(n)
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
            if not params.has_key(param_type):
                params[param_type] = []

            # see dir(mod_obj.Get_Parameters().Get_Parameter(0))
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
parser.add_argument('--libpath', dest='libpath', default='/usr/local/lib/saga', help='path to shared object library files')
parser.add_argument('--lib', dest='lib', help='parse given library only')
parser.add_argument('--mod', dest='mod', help='parse given module only')
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
    if args.mod and not re.match(r'^%s_[0-9]+$' % util.lib_name_from_so(fname), args.mod):
        continue

    if fname[-3:] == '.so':
        print 'parsing %s/%s ...' % (args.libpath,fname)

        # load library
        if args.skip and util.lib_name_from_so(fname) in args.skip.split(','):
            print "SKIPPING library %s as requested ..." % util.lib_name_from_so(fname)
            continue
        else:
            saga_api.SG_Get_Module_Library_Manager().Add_Library('%s/%s' % (args.libpath,fname))

        # define shortcut to library object
        lib_obj = saga_api.SG_Get_Module_Library_Manager().Get_Library(0)

        # define unique name for library
        lib_name = util.lib_name_from_so('%s/%s' % (args.libpath,fname))

        # define library title as we will use it more than once
        lib_title = util.cstr_2_str(lib_obj.Get_Name())

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
            'doc_Links' : {},    # will be filled while parsing modules
        }

        # resolve WIKI link if any
        if wikilinks.has_key(lib_name):
            libraries[lib_title]['WIKI_Link'] = wikilinks[lib_name]
        else:
            libraries[lib_title]['WIKI_Link'] = None

        # loop through library modules and collect details
        modules = {}
        for i in range(0,libraries[lib_title]['Get_Count']):
            # load module
            mod_obj = saga_api.SG_Get_Module_Library_Manager().Get_Module(lib_name, i)

            # make sure that module is valid
            if not u'Get_Name' in dir(mod_obj):
                continue

            # skip module if needed
            if args.mod and "%s_%s" % (lib_name, i) != args.mod:
                continue

            # remember module details - see dir(mod_obj)
            #print "DEBUG: %s_%s" % (lib_name, i)
            details = {
                'Get_Author' : util.cstr_2_str(mod_obj.Get_Author()),
                'Get_Description' : util.cstr_2_str(mod_obj.Get_Description()),
                'Get_ID' : mod_obj.Get_ID(),
                'Get_Icon' : mod_obj.Get_Icon(),
                'Get_MenuPath' : util.cstr_2_str(mod_obj.Get_MenuPath()),
                'Get_Name' : util.cstr_2_str(mod_obj.Get_Name()),
                'Get_Parameters' : util.parse_parameters(mod_obj),
                'Get_Parameters_Count' : mod_obj.Get_Parameters_Count(),
                'Get_Type' : mod_obj.Get_Type(),
                'is_Grid' : mod_obj.is_Grid(),
                'is_Interactive' : mod_obj.is_Interactive(),
                'needs_GUI' : False if not hasattr(mod_obj,'needs_GUI') else mod_obj.needs_GUI()    # introduced in https://sourceforge.net/p/saga-gis/code-0/2111/
            }

            # replace \n  with <br> in module description
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
            if wikilinks.has_key("%s_%s" % (lib_name,i)):
                details['WIKI_Link'] = wikilinks["%s_%s" % (lib_name,i)]
            else:
                details['WIKI_Link'] = None

            # define module title that will be used in index and a2z pages consisting of module name and interactive switch
            module_title = "%s%s" % (
                util.cstr_2_str(mod_obj.Get_Name()),
                ' (interactive)' if details['is_Interactive'] else ''
            )

            # remember links to module docs by title
            libraries[lib_title]['doc_Links'][module_title] = '%s_%s.html' % (lib_name, i)

            # fill a2z index, use list approach to ensure thate duplicate module names in different libraries don't get lost
            if not a2z.has_key(module_title):
                a2z[module_title] = []
            a2z[module_title].append('<tr><td><a href="%s">%s</a></td><td class="menuPath">%s</td></tr>' % (
                '%s_%s.html' % (lib_name, i),
                module_title,
                details['Full_Menu_Path']
            ))

            # define module type
            if details['is_Interactive'] and details['is_Grid']:
                TPL_TERMS['Specification'] = "grid, interactive"
            elif details['is_Interactive']:
                TPL_TERMS['Specification'] = "interactive"
            elif details['is_Grid']:
                TPL_TERMS['Specification'] = "grid"
            else:
                pass    # nothing else for now

            # unload module
            mod_obj.Destroy()

            # create module page
            TPL_TERMS['Get_Name'] = module_title
            TPL_TERMS['Get_Author'] = details['Get_Author']
            TPL_TERMS['Get_ID'] = details['Get_ID']
            TPL_TERMS['Get_Description'] = details['Get_Description']
            TPL_TERMS['Get_Description_HTML'] = details['Get_Description_HTML']
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
                if details['Get_Parameters'].has_key(section):
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

            # list modules with clashing is_Interactive and needs_GUI switches
            if not details['is_Interactive'] == details['needs_GUI']:
                debug_log.write("DEBUG: %s has is_Interactive=%s and needs_GUI=%s\n" % (
                    module_title,details['is_Interactive'],details['needs_GUI']
                ))
                has_debug = True

            # resolve saga_cmd usage for modules that do not need the GUI or are non-interactive
            if not details['is_Interactive']:
                proc = subprocess.Popen(['saga_cmd', lib_name, str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = proc.communicate()
                if err:
                    if details['needs_GUI']:
                        # set GUI hint as cmd usage
                        TPL_TERMS['Saga_Cmd'] = re.sub('Error: ','',err)
                    else:
                        print "ERROR: saga_cmd %s %s " % (lib_name,i)
                        error_log.write("ERROR: saga_cmd %s %s\n" % (lib_name,i))
                        error_log.write("       %s\n" % err)
                        TPL_TERMS['Saga_Cmd'] = "ERROR: %s" % err
                if out and not details['needs_GUI']:
                    usage = '\n'.join(out.split('\n')[16:])
                    usage = re.sub("<","&lt;", usage)

                    # fix missing lib_name and lib number for saga_cmd help prior to 2.1.3
                    if not re.search('saga_cmd %s %s' % (lib_name,i), usage):
                        usage = re.sub("saga_cmd", "saga_cmd %s %s" % (lib_name,i), usage)

                    # mark command
                    usage = re.sub('saga_cmd %s %s' % (lib_name,i),'<strong>saga_cmd %s %s</strong>' % (lib_name,i), usage)

                    if usage[:5] != "Usage":
                        error_log.write("NOTICE: saga_cmd %s %s has unknown usage string:\n%s\n\n" % (lib_name,i,usage))
                        print "NOTICE: saga_cmd %s %s has unknown usage string. Please check." % (lib_name,i)
                    TPL_TERMS['Saga_Cmd'] = "%s" % (
                        usage
                    )
            else:
                TPL_TERMS['Saga_Cmd'] = 'this interactive module can not be executed.'

            # add backlink
            TPL_TERMS['BACK_Link'] = "./%s.html" % lib_name
            TPL_TERMS['BACK_Text'] = lib_title

            # resolve module template
            s = Template(util.read_template('./templates/module.tpl'))
            o = open("%s/%s_%s.html" % (HTML_PATH,lib_name,i), "w")
            o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
            o.close()
            print "created %s/%s_%s.html" % (HTML_PATH,lib_name,i)

        # unload library
        saga_api.SG_Get_Module_Library_Manager().Del_Library(0)

        # create index page for modules in library
        TPL_TERMS['Module_Links'] = ''
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

        # set links to module pages
        order = libraries[lib_title]['doc_Links'].keys()
        order.sort()
        for mod_name in order:
            TPL_TERMS['Module_Links'] += "<li><a href='%s'>%s</a></li>" % (
                libraries[lib_title]['doc_Links'][mod_name],
                mod_name
            )

        # resolve library template
        s = Template(util.read_template('./templates/library.tpl'))
        o = open("%s/%s.html" % (HTML_PATH,lib_name), "w")
        o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
        o.close()
        print "created %s/%s.html" % (HTML_PATH,lib_name)

# create index page for libraries
TPL_TERMS['Library_Links'] = ''
if args.debugjson:
    TPL_TERMS['Debug_JSON'] = util.as_json(libraries)

# set links to library pages
order = libraries.keys()
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
o = open("%s/index.html" % (HTML_PATH), "w")
o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
o.close()
print "created %s/index.html" % (HTML_PATH)

# create a2z index page
TPL_TERMS['A2Z_Links'] = ''

order = a2z.keys()
order.sort()
for name in order:
    TPL_TERMS['A2Z_Links'] += "%s\n" % ('\n'.join(a2z[name]))

# resolve a2z template
s = Template(util.read_template('./templates/a2z.tpl'))
o = open("%s/a2z.html" % (HTML_PATH), "w")
o.write(s.safe_substitute(TPL_TERMS).encode('utf8'))
o.close()
print "created %s/a2z.html" % (HTML_PATH)

# copy lib/ and icons/ directories to html-path
print "\ncopying ./html/lib/ and ./html/icons/ directory to %s ..." % HTML_PATH
for subdir in ('lib','icons'):
    shutil.rmtree("%s/%s" % (HTML_PATH,subdir), True)
    shutil.copytree("./html/%s" % subdir, "%s/%s" % (HTML_PATH,subdir))
    shutil.rmtree("%s/%s/.svn" % (HTML_PATH,subdir), True)

# finish error and debug messages
error_log.close()
debug_log.close()

if has_errors:
    print "\nlogged ERRORS to error_log.txt"
if has_debug:
    print "\nlogged DEBUG messages to debug_log.txt"

"""

saga_api.SG_Get_Module_Library_Manager().Add_Library('/usr/local/lib/saga/libcontrib_a_perego.so')
mod_obj = saga_api.SG_Get_Module_Library_Manager().Get_Module('contrib_a_perego', 0)

"""
