import tempfile
import os
import sys
import logging
import argparse
import re
import javalang
from collections import defaultdict

# stores all lines of all files in a big two-level dictionary
all_files = defaultdict(dict)

# stores and tracks state of potential memory leaks in two-level dictionary
#    key1: file
#    key2: name assoc with leak
leaks = defaultdict(dict)

# stores the outer classes info for field declarations 
# key: field declarations
# value: a list holding outer classes info [class name, class line number, file of this class]
outerClasses = defaultdict(list)

# stores the function call graph for each function of each class in each file
# we only need a limited version of function call graphs so only calls to the class's own methods are tracked
#
# functionCallGraph[file][class][class method] = {}, where the dictionary stores all the class's own methods being called
funcCallGraph = defaultdict(dict)

# RE picks up static field declarations
staticfielddecl = '(static\s+(\w+)\s+(\w+)\s*(=([^;]+))?;)'

# Lifecycle methods
lifecycle = ['onCreate', 'onStart', 'onRestart', 'onResume', 'onPause', 'onStop', 'onDestroy']
allocation_cycles = ['onCreate', 'onStart', 'onRestart', 'onResume']
deallocation_cycles = ['onPause', 'onStop', 'onDestroy']

# Pattern type
pattern_types = ['STATIC FIELD', 'ANON THREAD', 'THREAD']

# Our toplevel driver
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', help="print ASTs")
    parser.add_argument("app_dir", type=str, help="a pathanme")
    args = parser.parse_args()

    e = os.path.expanduser(args.app_dir)
    g = os.walk(e)
    analysisfiles = extract_analysisfiles(g)
    #print(analysisfiles['classfiles'][11])
    #classes = [file[file.rfind('/'):] for file in analysisfiles['classfiles']]

    #print("java class files of interest: \n {} \n".format(classes))
    #print("manifests: \n {} \n".format(analysisfiles['manifests']))

    #for file in analysisfiles['classfiles']:
    file_analysis(analysisfiles['classfiles'][2], args.a)
        #file_analysis(file, args.a)
    print(funcCallGraph)
    #print(leaks)
    #flatten_leaks(leaks)
    #report_leaks(leaks)
    

def extract_analysisfiles(walk):
    """
    walk: a generator for a filesystem walk
    side effects: fills all_files with mapping from file/linenumber to line contents
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

    for file in app['classfiles']:
        with open(file, 'r') as fd:
            all_lines = fd.readlines()
            lineNum = 1
            for eachLine in all_lines:
                all_files[file][lineNum] = eachLine
                lineNum += 1
    return app

def find_java_decls(file):
    """
    Deprecated:

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

def file_analysis(file, aflag):
    with open(file, 'r') as fd:
        code_contents = fd.read()
        #print(code_contents)
        tree = gen_java_ast(code_contents)
        if aflag:
            print_ast(tree)
        gen_func_call_graph(file, tree)
        lifecycle_nodes = get_lifecycle_nodes(tree)
        static_fields = find_leak_preconditions(tree, lifecycle_nodes, file)
        find_leak_fixes(tree, lifecycle_nodes, static_fields, file)

def gen_java_ast(code_contents):
    """
    code_contents: string of valid java code
    returns: the java AST genertaed by javaparser library
    """
    tokens = javalang.tokenizer.tokenize(code_contents)
    #copy = list(tokens)
    #print(copy)
    parser = javalang.parser.Parser(tokens)
    return parser.parse()

def print_ast(tree):
    """
    tree: javaparser ast
    side effects: prints the AST with indentation to show children
    """
    for path, node in tree:
        spacestr = ""
        for i in range(len(path)):
            spacestr+="    "
        print("{}{} {}".format(spacestr, node, node.position))

def print_2d_dict(d):
    for k,v in d.items():
        print(k[k.rfind('/'):])
        for k2, v2 in v.items():
            print("    {}: {}".format(k2,v2))
        print("\n")

def flatten_leaks(d):
    for k,v in d.items():
        for k2, v2 in v.items():
            if(v2[1]):
                if v2[0] == 'STATIC FIELD':
                    if(type(v2[1]) == javalang.tree.Literal):
                        v2[1] = None
                        continue
                    known_reference = False
                    for path, node in v2[1].filter(javalang.tree.This):
                        outerclass_file = outerClasses[k2][2]
                        outerclass_pos = outerClasses[k2][1]
                        outerclass_line = all_files[outerclass_file][outerclass_pos]
                        outerclass_name = outerClasses[k2][0]

                        if "activity" in outerclass_line.lower():
                            warning = "Warning: static field {} likely leaks a reference (line {}) to enclosing class {} (line {}) which is very likely an activity class".format(k2, v2[2], outerclass_name, outerclass_pos)
                        else:
                            warning = "Warning: static field {} likely leaks a reference (line {}) to enclosing class.".format(k2, v2[2])
                        v2[1] = warning
                        known_reference = True
                    if(not known_reference):
                        warning = "Warning: use of static field {} (line {}) not advisable.".format(k2, v2[2])
                        v2[1] = warning

                if v2[0] == 'THREAD':
                    warning = "Warning: thread started (line {}) but not stopped. Thread resource possibly leaked.".format(v2[2])
                    v2[1] = warning
                if v2[0] == 'ANON THREAD':
                    warning = "Warning: anonymous thread started (line {}) but not stopped. Thread resource possibly leaked.".format(v2[2])
                    v2[1] = warning
                if v2[0] == 'LISTENER':
                    warning = "Warning: listener registered (line {}) but not unregistered after onPause(). Resource possibly leaked.".format(v2[2])
                    v2[1] = warning


def report_leaks(d):
    for k,v in d.items():
        filename = k[k.rfind('/'):]
        print("Class: {}: ".format(filename))
        for k2, v2 in v.items():
            if(v2[1]):
                print("    * "+v2[1])
        print("\n")

def get_lifecycle_nodes(tree):
    """
    tree: node in javaparser AST
    returns:
        lifecycle_nodes: dict containing mapping from lifecycle method names to
        the node in ths AST defining the method
    """
    lifecycle_nodes = {}
    for path, node in tree.filter(javalang.tree.MethodDeclaration):
        if(node.name in lifecycle):
            #print(node.name)
            lifecycle_nodes[node.name] = node
    return lifecycle_nodes

def find_leak_preconditions(tree, lifecycle_nodes, file):
    """
    tree: javalang CompilationUnit
    lifecycle_nodes: map from lifecycle names to their AST nodes
    file: the file containing CompilationUnit

    So far will retrieve the static fields declarations and track them
    in leaks dict.
    """
    static_fields = find_static_fields_from_name(tree, file)
    # updates which patterns to track
    for n,t,i,l in static_fields:
        leaks[file][n] = [t,i,l]

    process_anonymousclass(tree, file)
    process_innerclass(tree,file)

    # analyze the first half of lifecycle
    for method in allocation_cycles:
        if method in lifecycle_nodes.keys():
            node = lifecycle_nodes[method]
            assigns = find_static_assignments(node, static_fields, file)
            threads = find_thread_start(node, file)
            regs = find_registers(tree, file)
    return static_fields

def find_leak_fixes(tree, lifecycle_nodes, static_fields, file):
    for method in deallocation_cycles:
        if method in lifecycle_nodes.keys():
            node = lifecycle_nodes[method]
            assigns = find_static_assignments(node, static_fields, file)
            threads = find_thread_stop(node, file)
            find_unregisters(tree, file)

def find_fields(tree, file) :
    """
    tree: javaland AST
    returns:
        fields: list of fields belonging to classes in tree
                (name, initializer value, linenumber in file)
    """
    fields = []

    for path, classnode in tree.filter(javalang.tree.ClassDeclaration):
        outer_pos = classnode.position[0]
        outer_name = classnode.name
        
        for path, node in classnode.filter(javalang.tree.FieldDeclaration):
            if(type(node.type) == javalang.tree.ReferenceType):
                fields.append((node.declarators[0].name, node.declarators[0].initializer, node.position))
                outerClasses[node.declarators[0].name] = [outer_name, outer_pos, file]
                #print("Name={} dimensions={} initializer={} {} {}".format(node.declarators[0].name, \
                #node.declarators[0].dimensions, node.declarators[0].initializer,\
                #node.type, node.type.arguments))
    return fields

def find_thread_start(tree, file) :
    """
    tree: javalang AST node
    returns: list of threads started in the node
             (leak pattern name, type leaked, linenumber)
    """
    thread_pos = []
    start_inovoc_pattern = re.compile('([\w\(\)\.]+)\.start')
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if (node.member == 'start'):
            line = all_files[file][node.position[0]]
            pat_type = "THREAD"
            if (javalang.tree.ClassCreator == type(path[-2])): # Parent is ClassCreator
                #print("Thread is in abstract class. Likely leak at ", node.position[0])
                pat_type = "ANON THREAD"
            leak_pattern_name = start_inovoc_pattern.findall(line)[0]
            thread_pos.append((leak_pattern_name, pat_type, "THREAD", node.position[0]))

    for n,t,v,l in thread_pos:
        leaks[file][n] = [t,v,l]
    return thread_pos

def find_registers(tree, file) :
    """
    tree: javalang AST node
    returns: list of listeners et al registered in the node
             (leak pattern name, type leaked, linenumber)
    """
    regs = []
    start_inovoc_pattern = re.compile('([\w\(\)\.]+)\.register')
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if (node.member == 'register'):
            line = all_files[file][node.position[0]]
            pat_type = "LISTENER"
            leak_pattern_name = start_inovoc_pattern.findall(line)[0]
            regs.append((leak_pattern_name, pat_type, "LISTENER", node.position[0]))
    for n,t,v,l in regs:
        leaks[file][n] = [t,v,l]
    return regs

def find_thread_stop(tree, file) :
    """
    tree: javalang AST node
    returns: list of threads stopped in the node
             (leak pattern name, type leaked, linenumber)
    """
    thread_pos = []
    stop_inovoc_pattern = re.compile('([\w\(\)\.]+)\.interrupt')
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if (node.member == 'interrupt'):
            line = all_files[file][node.position[0]]
            pat_type = "THREAD"
            if (javalang.tree.ClassCreator == type(path[-2])): # Parent is ClassCreator
                #print("Thread is in abstract class. Likely leak at ", node.position[0])
                pat_type = "ANON THREAD"
                start = 0
            leak_pattern_name = stop_inovoc_pattern.findall(line)[0]
            thread_pos.append((leak_pattern_name, pat_type, None, node.position[0]))
    for n,t,v,l in thread_pos:
        leaks[file][n] = [t,v,l]
    return thread_pos

def find_unregisters(tree, file) :
    """
    tree: javalang AST node
    returns: list of listeners et al registered in the node
             (leak pattern name, type leaked, linenumber)
    """
    regs = []
    start_inovoc_pattern = re.compile('([\w\(\)\.]+)\.unregister')
    for path, node in tree.filter(javalang.tree.MethodInvocation):
        if (node.member == 'unregister'):
            line = all_files[file][node.position[0]]
            pat_type = "LISTENER"
            leak_pattern_name = start_inovoc_pattern.findall(line)[0]
            regs.append((leak_pattern_name, pat_type, None, node.position[0]))
    for n,t,v,l in regs:
        leaks[file][n] = [t,v,l]
    return regs

def find_static_fields_from_name(tree, file):
    """
    tree: javalang AST node
    file: filename containing the code for tree
    returns: list of fields that are delared as static
             (name, initializer, linnumber in file)
    """
    names = find_fields(tree, file)
    static_fields = []
    static_pat = re.compile('((\w*\s+)*)static ')
    for name, init, pos in names:
        linenum = pos[0]
        x = all_files[file][linenum]
        if(static_pat.match(x)):
            static_fields.append((name, "STATIC FIELD", init, linenum))
    return static_fields

def find_static_assignments(tree, static_fields, file):
    """
    tree: javalang AST node
    static_fields: list of static fields to track state for
    returns:
        assignments: list of assignments to those static fields
    """
    assignments = []
    for path, node in tree.filter(javalang.tree.Assignment):
        if(type(node.expressionl) == javalang.tree.MemberReference):
            ref = node.expressionl
            if ref.member in [f[0] for f in static_fields]:
                assignments.append((ref.member, "STATIC FIELD", node.value, ref.position[0]))

    for n,t,v,l in assignments:
        leaks[file][n] = [t,v,l]

    return assignments

def process_innerclass(tree, file):
    """
    check if there is any non-static inner class which is potentially a source
    of memory leak
    """

    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        parent_pos = node.position[0]
        parent_name = node.name
        parent_line = all_files[file][parent_pos]
        parent_activity = False

        if 'activity' in parent_line.lower():
            parent_activity = True

        for path, child in node.filter(javalang.tree.ClassDeclaration):
            if child is not node:
                child_pos = child.position[0]
                child_name = child.name
                child_line = all_files[file][child_pos]
                child_static = True
                if re.search("\s+static\s+class", child_line) is None:
                    child_static = False

                if parent_activity and not child_static:
                    leaks[file][child_name] = ["INNER CLASS", "parent", child_line]
                    #print(file[file.rfind('/'):])
                    warning = "Warning: class "+parent_name+" (line "+str(parent_pos)+") has a non-static inner "\
                          +"class "+child_name+" (line "+str(child_pos)+"), and there is a high risk of memory leak "\
                          +"because "+parent_name+" is likely an activity class and "+child_name+" holds a "\
                          +"reference to it" #% (parent_name, parent_pos, child_name, child_pos, parent_name, child_name)
                    #print(warning)
                    leaks[file][child_name] = ["INNER CLASS", warning, child_line]
                elif not parent_activity and not child_static:
                    #print(file[file.rfind('/'):])
                    warning = "Warning: class "+parent_name+" (line "+str(parent_pos)+") has a non-static inner "\
                          +"class "+child_name+" (line "+str(child_pos)+"), and there is a potential risk of memory leak "\
                          +"because "+child_name+" holds a "\
                          +"reference to "+parent_name # % (parent_name, parent_pos, child_name, child_pos, child_name, parent_name))
                    #print(warning)
                    leaks[file][child_name] = ["INNER CLASS", warning, child_line]

def process_anonymousclass(tree, file):
    anonymous_class_rex = "new\s+.*\(.*\)\s*{"
    with open(file, 'r') as fd:
        all_lines = fd.readlines()
    startPos = len(all_lines)

    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        parent_pos = node.position[0]
        parent_name = node.name
        parent_line = all_files[file][parent_pos]
        parent_activity = False

        if 'activity' in parent_line.lower():
            parent_activity = True

        for path, child in node.filter(javalang.tree.ClassCreator):
            for path, nextNode in child:
                if nextNode.position is not None:
                    startPos = nextNode.position[0]
                    break
            while startPos >= 2:
                cur_line = all_files[file][startPos]
                prev_line = all_files[file][startPos-1]
                line = prev_line +  cur_line
                if re.search(anonymous_class_rex, line) is not None:
                    if parent_activity:
                        #print(file[file.rfind('/'):])
                        warning = "Warning: class "+parent_name+" (line "+str(parent_pos)+") has an anonymous inner "\
                              +"class (line "+str(startPos-1)+"), and there is a high risk of memory leak "\
                              +"because "+parent_name+" is likely an activity class and the anonymous inner class holds a "\
                              +"reference to it" #% (parent_name, parent_pos,startPos-1, parent_name))
                        #print(warning)
                        leaks[file][line] = ["ANON CLASS", warning, startPos-1]
                    else:
                        #print(file[file.rfind('/'):])
                        warning = "Warning: class "+parent_name+" (line "+str(parent_pos)+") has an anonymous inner "\
                                +"class (line "+str(startPos-1)+"), and there is a potential risk of memory leak "\
                                +"because the anonymous inner class holds a "\
                                +"reference to "+parent_name #% (parent_name, parent_pos,startPos-1, parent_name))
                        #print(warning)
                        leaks[file][line] = ["ANON CLASS", warning, startPos-1]
                    break

                startPos -= 1

def gen_func_call_graph(file, tree):
    # funcCallGraph[file][class][method] = {}

    for path, classNode in tree.filter(javalang.tree.ClassDeclaration):
        funcCallGraph[file][classNode.name] = dict()

        for path, method in classNode.filter(javalang.tree.MethodDeclaration):
            funcCallGraph[file][classNode.name][method.name] = set()

    for path, classNode in tree.filter(javalang.tree.ClassDeclaration):
        for path, method in classNode.filter(javalang.tree.MethodDeclaration):
            for path, call in method.filter(javalang.tree.MethodInvocation):
                call_name = call.member
                if call_name in funcCallGraph[file][classNode.name]:
                    funcCallGraph[file][classNode.name][method.name].add(call_name)




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
    """
    for checking work on static declaration pattern matching
    """
    for file in files:
        find_java_decls(file)



if __name__ == "__main__":
    main()
