import tempfile
import os
import sys
import logging
import argparse
import re

# RE picks up static field declarations
staticfielddecl = '(static\s+(\w+)\s+(\w+)\s*(=([^;]+))?;)'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app_dir", type=str, help="a pathanme")
    args = parser.parse_args()

    e = os.path.expanduser(args.app_dir)
    g = os.walk(e)
    analysisfiles = extract_analysisfiles(g)
    classes = [file[file.rfind('/'):] for file in analysisfiles['classfiles']]
    print("java class files of interest: \n {} \n".format(classes))
    print("manifests: \n {} \n".format(analysisfiles['manifests']))

    findall_java_decls(analysisfiles['classfiles'])

def extract_analysisfiles(walk):
    """
    files: a generator for a filesystem walk
    returns:
        app: a dictionary containing the app manifest and java class files
    """
    app = { 'classfiles': [], 'manifests': [] }
    for dir,dirs,files in walk:
        if dir.find('test') == -1 and dir.find('Test') == -1 and dir.find('build') == -1:
            for file in files:
                if file.endswith('.java') and file != 'R.java' and file != 'BuildConfig.java':
                    app['classfiles'].append(dir+'/'+file)
                if file == 'AndroidManifest.xml':
                    app['manifests'].append(dir+'/'+file)
    return app

def find_java_decls(file):
"""
walks through file line by line and looks for static field declarations.
If found, state of the field is tracked through the rest of the walk 
in staticfields dict.
"""
    staticfields = {}
    with open(file, 'r') as fd:
        while True:
            x = fd.readline()
            if x == '':
                break;
            decl = re.findall(staticfielddecl,x)
            if(decl):
                staticfields[decl[0][2]] = decl[0][4]
            for s in staticfields.keys():
                ass = re.findall(fmt_ass(s),x)
                if(ass):
                    print(ass[0][0])
                    staticfields[s] = ass[0][1]

def fmt_ass(field):
    return "({}\s*=([^;]+);)".format(field)

def findall_java_decls(files):
    for file in files:
        find_java_decls(file)
    


if __name__ == "__main__":
    main()
