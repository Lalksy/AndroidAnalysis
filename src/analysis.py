import tempfile
import os
import sys
import logging
import argparse
import re
import javalang

# RE picks up static field declarations
staticfielddecl = '(static\s+(\w+)\s+(\w+)\s*(=([^;]+))?;)'

# Lifecycle methods
lifecycle = ['onCreate', 'onStart', 'onRestart', 'onResume', 'onPause', 'onStop', 'onDestroy']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app_dir", type=str, help="a pathanme")
    args = parser.parse_args()

    e = os.path.expanduser(args.app_dir)
    g = os.walk(e)
    analysisfiles = extract_analysisfiles(g)
    #classes = [file[file.rfind('/'):] for file in analysisfiles['classfiles']]

    #print("java class files of interest: \n {} \n".format(classes))
    #print("manifests: \n {} \n".format(analysisfiles['manifests']))

    # findall_java_decls(analysisfiles['classfiles'])

    tree = gen_java_ast(analysisfiles['classfiles'][9])
    print_ast(tree)

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

def gen_java_ast_simple(file):
    """
    Uses javalang to generate a java 8 AST
    """
    print(file)

    with open(file, 'r') as fd:
        code_contents = fd.read()
        tree = javalang.parse.parse(code_contents)
        for path, node in tree:
            spacestr = ""
            name = ""
            for i in range(len(path)):
                spacestr+="    "
            if (type(node) == javalang.tree.MethodDeclaration):
                name = node.name
            print("{}{} {}".format(spacestr, node, name))

def gen_java_ast(file):
    """
    generates and returns the java ast using javaparser library
    """
    with open(file, 'r') as fd:
        code_contents = fd.read()
        tokens = javalang.tokenizer.tokenize(code_contents)
        parser = javalang.parser.Parser(tokens)
        return parser.parse()

def print_ast(tree):
    """
    prints the ast with indentation to show children
    """
    for path, node in tree:
        spacestr = ""
        for i in range(len(path)):
            spacestr+="    "
        print("{}{}".format(spacestr, node))

def build_sym_table(tree) :
    """
    Incomplete method. Working on building table.
    """
    for path, node in tree:
        spacestr = ""
        name = ""
        value = ""
        for i in range(len(path)):
            spacestr+="    "
        if (type(node) == javalang.tree.CompilationUnit):
            name = node.name
        if (type(node) == javalang.tree.MethodDeclaration):
            name = node.name
        if (type(node) == javalang.tree.Literal):
            value = node.value
        print("{}{} {}{}".format(spacestr, node, name, value))
    return

def body(file):
    """
    Incomplete method for extracting a block. Prototype for thoughts. Walks through lines of a file.
    classbody is True when the current line is part of the class body def.
    """
    stack = []
    classbodyopen = False
    with open(file, 'r') as fd:
        while True:
            x = fd.readline()
            if x == '':
                break;
            ans = re.findall('{|}', x)
            for b in ans:
                if b == '{':
                    if not classbodyopen:
                        classbodyopen = True
                        print('class body open')
                    stack.append(b)
                else:
                    if stack:
                        stack.pop()
                    else:
                        print('SYNTAX ERROR')
            if classbodyopen and not stack:
                classbodyopen = False

def fmt_ass(field):
    return "({}\s*=([^;]+);)".format(field)

def findall_java_decls(files):
    for file in files:
        find_java_decls(file)



if __name__ == "__main__":
    main()
