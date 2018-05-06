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
allocation_cycles = ['onCreate', 'onStart', 'onRestart', 'onResume']
deallocation_cycles = ['onPause', 'onStop', 'onDestroy']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app_dir", type=str, help="a pathanme")
    args = parser.parse_args()

    e = os.path.expanduser(args.app_dir)
    g = os.walk(e)
    analysisfiles = extract_analysisfiles(g)
    classes = [file[file.rfind('/'):] for file in analysisfiles['classfiles']]

    #print("java class files of interest: \n {} \n".format(classes))
    #print("manifests: \n {} \n".format(analysisfiles['manifests']))

    # findall_java_decls(analysisfiles['classfiles'])

    for file in analysisfiles['classfiles']:
    #file = analysisfiles['classfiles'][0]
        print("---AST {}".format(file[file.rfind('/'):]))
        file_analysis(file)
        #print("---regexp")
        #find_java_decls(file)
        #print("\n")

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

def file_analysis(file):
    with open(file, 'r') as fd:
        code_contents = fd.read()
        tree = gen_java_ast(code_contents)
        #print_ast(tree)
        lifecycle_nodes = get_lifecycle_nodes(tree)
        find_leak_preconditions(tree, lifecycle_nodes, file)

def gen_java_ast(code_contents):
    """
    generates and returns the java ast using javaparser library
    """
    #print(code_contents)
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
        print("{}{} {}".format(spacestr, node, node.position))

def get_lifecycle_nodes(tree):
    lifecycle_nodes = {}
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        if(node.name in lifecycle):
            #print(node.name)
            lifecycle_nodes[node.name] = node
    return lifecycle_nodes

def find_leak_preconditions(tree, lifecycle_nodes, file):
    static_fields = find_static_fields_from_name(tree, file)
    #print(static_fields)
    for method in allocation_cycles:
        if method in lifecycle_nodes.keys():
            node = lifecycle_nodes[method]
            threads = find_thread_start(node)
            print(threads)

def find_fields(tree) :
    """
    Walks over ast and returns the name of any fields
    """
    fields = []
    for path, node in tree.filter(javalang.tree.FieldDeclaration):
        if(type(node.type) == javalang.tree.ReferenceType):
            fields.append((node.declarators[0].name, node.declarators[0].initializer, node.position))
            #print("Name={} dimensions={} initializer={} {} {}".format(node.declarators[0].name, \
            #node.declarators[0].dimensions, node.declarators[0].initializer,\
            #node.type, node.type.arguments))
    return fields

def find_thread_start(tree) :
    """
    Walks over ast and returns pos of possibly leaked threads
    """
    thread_pos = []
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if (node.member == 'start'):
            if (javalang.tree.ClassCreator in [type(x) for x in path]):
                print("Thread is in abstract class. Likely leak at ", node.position[0])
            thread_pos.append(node.position[0])
    return thread_pos

def find_static_fields_from_name(tree, file):
    names = find_fields(tree)
    static_fields = []
    static_pat = re.compile('((\w*\s+)*)static ')
    for name, init, pos in names:
        with open(file, 'r') as fd:
            linenum = pos[0]-1
            lines = fd.readlines()
            x = lines[linenum]
            #print(x, linenum)
            if(static_pat.match(x)):
                static_fields.append((name, init, linenum))
    return static_fields

def build_sym_table(tree) :
    """
    Incomplete method. Working on building table.
    """
    for path, node in tree:
        spacestr = ""
        name = ""
        value = ""
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
