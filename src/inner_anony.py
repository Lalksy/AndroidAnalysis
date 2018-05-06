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
                    print(file)
                    print("Warning: class %s (line %d) has a non-static inner "
                          "class %s (line %d), and there is a high risk of memory leak "
                          "because %s is likely an activity class and %s holds a "
                          "reference to it" % (parent_name, parent_pos, child_name,
                            child_pos, parent_name, child_name))

                elif not parent_activity and not child_static:
                    print(file)
                    print("Warning: class %s (line %d) has a non-static inner "
                          "class %s (line %d), and there is a potential risk of memory leak "
                          "because %s holds a "
                          "reference to %s" % (parent_name, parent_pos, child_name,
                            child_pos, child_name, parent_name))

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
                        print(file)
                        print("Warning: class %s (line %d) has an anonymous inner "
                              "class (line %d), and there is a high risk of memory leak "
                              "because %s is likely an activity class and the anonymous inner class holds a "
                              "reference to it" % (parent_name, parent_pos,
                              startPos-1, parent_name))
                    else:
                        print(file)
                        print("Warning: class %s (line %d) has an anonymous inner "
                                "class (line %d), and there is a potential risk of memory leak "
                                "because the anonymous inner class holds a "
                                "reference to %s" % (parent_name, parent_pos,
                                startPos-1, parent_name))

                    break 

                startPos -= 1