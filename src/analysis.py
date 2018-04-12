import tempfile
import os
import sys
import logging
import argparse




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

if __name__ == "__main__":
    main()
