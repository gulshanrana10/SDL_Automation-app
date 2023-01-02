 #Title           :SDL TOOLKIT V22.9
#Author          :Gulshan Rana(CNS CN GS SS SDM T-6)
#Email           :gulshan.rana@nokia.com
#Date            :Sept-2022

import subprocess
import pexpect
import yaml
import os
import commands
import sys
import json
from time import sleep
import requests
from datetime import datetime as dtm
from prettytable import PrettyTable
from requests.packages.urllib3.exceptions import InsecureRequestWarning
global in_file

class SDL:
    def __init__(self, c):
        if not os.path.isfile("SDL_input.json"):
            print "\033[91m'SDL_input.json' file not found in current directory.\033[00m"
            sys.exit(1)
        self.data = json.load(open("SDL_input.json", ))     #generalise the input_file name
        self.base_dir = os.path.dirname(self.data["VNF"]["TPD"])
        self.sdl_dir = os.path.join(self.base_dir, "sdlmedia")
        self.logs = ""
        # self.log_file = ""
        self.options(c)

    def options(self, o):
        if not os.path.isdir("log"):
             os.mkdir('log')
        if o == '1':
            self.phase1()
        elif o == '2':
            self.terminate()
        elif o == '3':
            
            self.logs = open("{0}/log/SDL_instantiation_status_{1}.log".format(self.base_dir,dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
            self.check_status()
            self.logs.close()
        else:
            print ("\033[91mWrong Selection\033[00m")
            sys.exit(1)

    def phase1(self):
        # source rc file
        os.system('source {}'.format(self.data["rc"]))
        #self.get_output("source {}".format(self.data["rc"]))
        # self.log_file = "/tmp/SDL_VNF_deploy_test.log"
        
        self.logs = open("{}/log/SDL_VNF_prepare_{}.log".format(self.base_dir,dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
        self.create_flavors()
        m = self.untar_media()
        self.glance_image(m)
        self.pass_enc()
        self.tpd_validate()
        self.vnf_prepare()
        self.logs.close()

    def live_output(self, cmd):
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            out = process.stdout.readline()
            if out == '' and process.poll() is not None:
                break
            if out != '':
                sys.stdout.write(out.strip())
                print >> self.logs, (out.strip())
                sys.stdout.flush()
        rc = process.poll()
        return rc

    def terminate(self):
        pass

    # def phase2(self):
    #     # self.log_file = "/tmp/SDL_instantiate_test.log"
    #     self.logs = open("/tmp/SDL_instantiate_{}.log".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
    #     self.sdl_instantiate()
    #     self.logs.close()

    def check_status(self):
        print "#" * 80
        self.prBlue("[INFO]: Fetching SDL Instantiation status...")
        print "#" * 80
        
        os.chdir(os.path.join(self.sdl_dir, "orchestration", "sdl"))
        cmd = "python sdl_check_instantiation_status.py --TPD_files_path {0}".format(self.data["VNF"]["TPD"])
        
        pswd = raw_input("Enter 'sdladmin' password for TPD - {} >> ".format(self.data["VNF"]["TPD"]))
        child = pexpect.spawn(cmd)
        f = open("{0}/log/sdl_instantiation_status1.json".format(self.base_dir), 'w') #remove1
        while True: 
            ch = child.expect([u'yaml:', pexpect.TIMEOUT, pexpect.EOF])
            if ch == 0:
                child.sendline(pswd)
                child.logfile = f
            elif ch == 1:
                continue
            elif ch == 2:
                break
        self.prYellow(f)
        child.close()
        f.close()
        try:
            stat = json.load(open("{0}/log/sdl_instantiation_status.json".format(self.base_dir),'r' ))
        except ValueError:
            pass
        t = PrettyTable(
            ['LSDL', 'SDL', 'Confd vIP', 'Message', 'Description', 'ID', 'Status', 'Start-time', 'End-time'])
        t.align["Description"] = "l"
        for i in stat["deployment"]:
                 
            t.add_row([i["lsdlInstance"], i["sdlInstance"], i["confdVip"], i["message"], i["transaction"]["type"], i["transaction"]["id"], self.color_check(i["transaction"]["status"]), i["transaction"]["start-time"], i["transaction"]["end-time"]])
            for y in sorted(i['transaction']['jobs']['job'],key=lambda j: j["start-time"]):
                t.add_row(['', '', '', '', y['description'], y['id'], self.color_check(y['status']), y['start-time'],y['end-time']])
        #os.system('clear')
        self.prPurple(t)
        


    def color_check(self, s):
        s = str(s).upper()
        if s == "SUCCESS":
            r = "92"
        elif s == "FAIL" or s == "FAILED":
            r = "91"
        else:
            r = "95"
        return "\033[{0}m{1}\033[00m".format(r, s)

    def more(self):
        pass

    def get_output(self, cmd):
        self.prCyan("[CMD]: %s" % cmd)
        s, o = commands.getstatusoutput(cmd)
        for r in o.splitlines():
            self.prlogonly(r.strip())
        self.prlogonly("")
        '''if s!=0:   #if flavor already exist
            self.prRed("[FAIL]: Execution failed.")'''
            #self.exit1()
            #os.system('clear')
        return o

    def create_flavors(self):
        print "#" * 80
        self.prBlue("[INFO]: Creating flavors...")
        print "#" * 80
        # check if flavor already exists, if yes check for the configurations as per the input else ask user to continue
        for flavor, d in self.data["Flavor"].items():       
            self.prPurple("[INFO]: Checking for existing flavors...")
            s = self.get_output("openstack flavor list | grep -w {}".format(d["name"]))
            if not s.strip():
                self.prGreen("[INFO]: Creating flavor %s" % d["name"])
                cmd = "openstack flavor create {0} --vcpus {1} --disk {2} --ram {3}".format(
                    d["name"], d["vcpu"], d["disk"], d["ram"])
                self.get_output(cmd)
            else:
                x = s.replace("|", "").split()
                if int(x[2]) == d["ram"] and int(x[3]) == d["disk"] and int(x[5]) == d["vcpu"] and x[6] == 'True':
                    self.prYellow("[WARN]: %s already created and active." % d["name"])
                else:
                    self.prRed("[FAIL]: %s already exists with different configurations or is not public." % d["name"])
                             
                    self.exit1()
                    # c = raw_input("Enter '1' to create new flavor with name='%s_new' or CTRL+c to quit")
                    # if c.strip() == "1":
                    #     self.prGreen("[INFO]: Creating flavor %s_new" % flavor["name"])
                    #     cmd = "openstack flavor create {0}_new --vcpus {1} --disk {2} --ram {3}".format(
                    #         flavor["name"], flavor["vcpu"], flavor["disk"], flavor["ram"])
                    #     self.get_output(cmd)
                    # else:
                    #     self.exit1()
                
        self.prGreen("[INFO]: Flavor Creation completed!!!")
                
      

    def untar_media(self):
        print "#" * 80
        self.prBlue("[INFO]: Unzipping SDL Media...")
        print "#" * 80
        if not os.path.exists(self.data["media"]["cpio_file_path"]):
            self.prRed("[FAIL]: Media file path does not exists -> %s" % self.data["media"]["cpio_file_path"])
            self.exit1()
        if os.path.exists(self.sdl_dir):
            # check if media already unzipped
            if os.path.exists(os.path.join(self.sdl_dir, "orchestration")):
                self.prYellow("[WARN]: Media already unzipped.")
            os.chdir(self.sdl_dir)
        else:
            os.mkdir(self.sdl_dir)
            os.chdir(self.sdl_dir)
            self.prPurple("[INFO]: Unzipping SDL media file to directory '%s'" % self.sdl_dir)
            self.get_output("cpio -idm < %s" % self.data["media"]["cpio_file_path"])
        
        s = self.get_output("ls -l ")
        m = {}
        for r in s.splitlines():
            try:
                r = r.split()[8]
            except IndexError:
                continue
            if r.startswith("nokia") and r.endswith("qcow2"):
                m[self.get_name(r.split("-")[2])] = r
        if len(m.keys()) < 5:  #No. of images
            self.prRed("[FAIL]: Not all images found")
            self.exit1()
        self.prGreen("[INFO]: Media Unzipping completed!!!")
        return m

    def get_name(self, n): 
        if n == "operations":
            return "OPS"
        elif n == "realtimedatabase":
            return "RTDB"
        elif n == "telemetry":
            return "TELE"
        elif n == "notification":
            return "NTF"
        elif n == "diagnostics":
            return "DIAG"
        elif n == "AccessDB":
            return "ADB"
        elif n == "StorageDB":          #no ntfsync image
            return "SDB"

    def glance_image(self, m):
        print "#" * 80
        self.prBlue("[INFO]: Glancing images...")
        print "#" * 80
        # check if images already present openstack image list | grep -i nokia-sdl
        self.prYellow("[INFO]: Creation will take several minutes. Please wait.")
        images=["OPS", "RTDB", "TELE", "NTF", "DIAG"]
        for vm in images:
            self.prPurple("[INFO]: Checking for existing images...")
            try:
                s = self.get_output("openstack image list | grep -i {}".format(self.data["glance"][vm]))
                if not s.strip():
                    self.prGreen("[INFO]: Glancing image %s" % self.data["glance"][vm])
                    cmd = "glance image-create --name {0} --disk-format qcow2 --container-format bare " \
                          "--file {1}".format(self.data["glance"][vm], m[vm])   #path- sdlmedia
                    self.get_output(cmd)
                    #CREATE CHECK FUNCTION
                else:
                    d = s.replace("|", "").split()
                    if d[2] == "active":
                        self.prYellow("[WARN]: %s already created and active." % self.data["glance"][vm])
                    else:
                        self.prRed("[WARN]: %s already exists but not active." % self.data["glance"][vm])
                        self.exit1()
                        # c = raw_input("Enter '1' to create new image with name='%s_new' or CTRL+c to quit")
                        # if c.strip() == "1":
                        #     self.prGreen("[INFO]: Creating flavor %s_new" % flavor["name"])
                        #     cmd = "openstack flavor create {0}_new --vcpus {1} --disk {2} --ram {3}".format(
                        #         flavor["name"], flavor["vcpu"], flavor["disk"], flavor["ram"])
                        #     self.get_output(cmd)  
                        # else:
                        #     self.exit1()
            
            except KeyError as k:
                self.prRed("[FAIL]: Glance image name for %s vm not found" % k)
                self.exit1()
        self.check_images(m)
        
    def check_images(self,m):
        print "#" * 80
        self.prBlue("[INFO]: Checking completion of image creation...")
        print "#" * 80
        count=0
        images=["OPS", "RTDB", "TELE", "NTF", "DIAG"]
        for vm in images:
            
            try:
                s = self.get_output("openstack image list | grep -i {}".format(self.data["glance"][vm]))
                if s.strip():
                    d = s.replace("|", "").split()
                    if d[2] == "active":
                        count=count+1
                    else:
                        self.prRed("[WARN]: %s Unsuccessful Image Creation" % self.data["glance"][vm])
                        self.exit1()
                        # c = raw_input("Enter '1' to create new image with name='%s_new' or CTRL+c to quit")
                        # if c.strip() == "1":
                        #     self.prGreen("[INFO]: Creating flavor %s_new" % flavor["name"])
                        #     cmd = "openstack flavor create {0}_new --vcpus {1} --disk {2} --ram {3}".format(
                        #         flavor["name"], flavor["vcpu"], flavor["disk"], flavor["ram"])
                        #     self.get_output(cmd)
                        # else:
                        #     self.exit1()
                else:
                    self.prRed("[WARN]: %s isn't created" % self.data["glance"][vm])
                    self.exit1()
            except KeyError as k:
                self.prRed("[FAIL]: Glance image name for %s vm not found" % k)
                self.exit1()
        if count==len(images):
            self.prGreen("[INFO]: Glance creation successfull !!!")
            
    def pass_enc(self):
        self.prBlue("[INFO]: Initiating Password encryption...")
        self.prYellow("[INFO]: This will take few minutes. Please wait...")
        os.chdir(os.path.join(self.sdl_dir, "orchestration", "encryption"))
        password = self.data["VNF"]["enc-pass"]
        
        cmd = "python pass_encrypt.py {} --entropy".format(self.data["VNF"]["TPD"])
        self.prCyan("\n[CMD]: %s" % cmd)
        child = pexpect.spawn(cmd, encoding='utf-8')
        #child.logfile = self.logs
        while True:
            ch = child.expect([u':', pexpect.TIMEOUT, pexpect.EOF])
            if ch == 0:
                child.sendline(password)
            elif ch == 1:
                continue
            elif ch == 2:
                break
        self.prGreen("Encryption completed")
                
    def tpd_validate(self):
        print "#" * 80
        self.prBlue("[INFO]: Initiating TPD validation...")
        print "#" * 80
        path=os.path.join(self.sdl_dir,"orchestration","preparation_tools")
        os.chdir(path)
        cmd = "python prepare_VNF_inputs.py --TPD_path {} --vnf_type {} --validate_TPD".format(self.data["VNF"]["TPD"], self.data["VNF"]["vnf-type"])
        out=self.get_output(cmd)
        print(out)
        print "#" * 80
        self.prGreen("[INFO]: TPD Validation successfull !!!")
        print "#" * 80


    def vnf_prepare(self):
        self.prBlue("[INFO]: Verifying if stack exists already...")
        s = self.get_output("openstack stack list | grep -w sdl_cinder_{}".format(self.data["VNF"]["resource_suffix"]))
        if s.strip():
            x = s.replace("|", "").split()
            if x[3] == 'CREATE_COMPLETE':
                self.prYellow("[WARN]: '%s' Stack already exists..." % x[1])
                
            else:
                self.prYellow("[WARN]: %s already exists with different/incomplete configurations." % self.data["VNF"]["resource_suffix"])
                        
            return
        self.prBlue("[INFO]: Creating stack...")
        self.prYellow("[INFO]: Completion will take several minutes. Please wait.")
        os.chdir(os.path.join(self.sdl_dir, "orchestration","preparation_tools"))
        cmd = "python prepare_VNF_inputs.py --TPD_path {0} --openstack_env_file {1} --vnf_type {2} --resource_suffix {3}".format(self.data["VNF"]["TPD"],self.data["rc"],self.data["VNF"]["vnf-type"],self.data["VNF"]["resource_suffix"])
        self.prYellow("[INFO]: You can check the logs here -> %s" % os.path.join(self.sdl_dir, "orchestration", "preparation_tools", "log"))
        self.get_output(cmd)
        # self.live_output(cmd)
        sleep(20)
       # self.check_stack()
        

    def check_stack(self):
        self.prBlue("[INFO]: Verifying Stack creation......")
        s = self.get_output("openstack stack list | grep -w sdl_cinder_{}".format(self.data["VNF"]["resource_suffix"]))
        if not s.strip():
            self.prRed("[FAIL]: Stack not created")
            self.exit1()
        else:
            d = s.replace("|", "").split()
            if d[3] == "CREATE_COMPLETE":
                print "#" * 80
                self.prGreen("[PASS]: '%s' stack created successfully." % d[1])
                print "#" * 80
            else:
                self.prRed("[FAIL]: '%s' Stack not created completely. Stack Status --> %s" % (d[1], d[3]))
                self.exit1()

    def header_conf(self, t, txt):
        self.prlogonly("#" * 70)
        self.prlogonly("##" + "{:^66}".format(txt) + "##")
        self.prlogonly("##" + ' ' * 66 + "##")
        self.prlogonly("##" + (" Date : %s" % t.strftime("%d %b %Y %H:%M:%S")).ljust(66) + "##")
        self.prlogonly("#" * 70)
        self.prlogonly("\n")

    def http_status(self, code):
        if code == 401:
            self.prRed("[FAIL]: 401 - Authentication failure. Please check 'sdladmin' password.")
            self.exit1()
        elif code == 404:
            self.prPurple("[WARN]: No output received from server. 404 - Not Found")
            self.exit1()
        elif code != 200:
            self.prRed("[FAIL]: HTTP return Code = " + str(code))
            self.exit1()

    def exit1(self):
        self.prYellow("[LOGS] : Check logs here --> %s" % self.logs)
        sys.exit(1)

    def prRed(self, msg):
        print ("\033[91m{}\033[00m".format(msg))
        print >> self.logs, ("\033[91m{}\033[00m".format(msg))

    def prGreen(self, msg):
        print ("\033[92m{}\033[00m".format(msg))
        print >> self.logs, ("\033[92m{}\033[00m".format(msg))

    def prYellow(self, msg):
        print ("\033[93m{}\033[00m".format(msg))
        print >> self.logs, ("\033[93m{}\033[00m".format(msg))

    def prBlue(self, msg):
        print("\033[94m{}\033[00m".format(msg))
        print >> self.logs, ("\033[94m{}\033[00m".format(msg))

    def prPurple(self, msg):
        print("\033[95m{}\033[00m".format(msg))
        print >> self.logs, ("\033[95m{}\033[00m".format(msg))

    def prCyan(self, msg):
        # print("\033[96m{}\033[00m".format(msg))
        print >> self.logs, ("\033[96m{}\033[00m".format(msg))

    def prNC(self, msg):
        print msg
        print >> self.logs, msg

    def prborder(self):
        print "-" * 70
        print >> self.logs, "-" * 70

    def prheader(self):
        print "=" * 70
        print >> self.logs, "\n"
        print >> self.logs, "=" * 70
        print >> self.logs, "\n"

    def prlogonly(self, text):
        print >> self.logs, (text.encode('utf-8'))

class AEP:
    def __init__(self, ch):
        os.system("mkdir -p /tmp/AEP")
        self.confd_vip = ""
        self.diag_vip = ""
        self.lsdl = ""
        self.sdli = ""
        self.sdl_pass = ""
        self.logs = ""
        self.ref = ""
        self.input_file = "AEP_list.txt"
        self.get_details()
        self.options(ch)

    def get_details(self):
        print ("\033[96mEnter details...\033[00m")
        print ("\033[93m 1. Fetch from /sdlinst/TPD.yaml\033[00m")
        print ("\033[93m 2. Enter manually\033[00m")
        o = raw_input("Your choice: ")
        if o == '1':
            data = self.get_tpd()
            self.confd_vip = data["confd_vip"]
            self.diag_vip = data["diag_vip"]
            self.lsdl = data["lsdl_i"]
            self.sdli = data["sld_i"]
            self.sdl_pass = data["sdl_pass"]
        elif o == '2':
            self.confd_vip = raw_input("Enter Confd vIP: ")
            self.diag_vip = raw_input("Enter Diag vIP: ")
            self.lsdl = raw_input("Enter LSDL instance: ")
            self.sdli = raw_input("Enter SDL instance: ")
            self.sdl_pass = raw_input("Enter sdladmin user password: ")
        else:
            print ("\033[96mWrong selection --> %s\033[00m" % o)
            sys.exit()
        # Display values
        print "\033[96m[DATA]: Confd vIP     : {0}\033[00m".format(self.confd_vip)
        print "\033[96m[DATA]: Diag vIP      : {0}\033[00m".format(self.diag_vip)
        print "\033[96m[DATA]: SDL Instance  : {0}\033[00m".format(self.sdli)
        print "\033[96m[DATA]: LSDL Instance : {0}\033[00m".format(self.lsdl)
        raw_input("Press Enter to continue with these values or CTRL+C to quit...")

    def options(self, ch):
        if ch == '1':
            self.health_check_SDL()
        elif ch == '2':
            self.logs = open("/tmp/AEP/AEP_HC_level3_{}.txt".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
            self.get_AEPs()
            print "\033[93m[LOGS]: Refer logs --> {}\033[00m".format(self.logs.name)
            self.logs.close()
        elif ch == '3':
            if not os.path.isfile("AEP_list.txt"):
                print "\033[91m[FAIL]: 'AEP_list.txt' file not found in current directory.\033[00m"
                sys.exit(1)
            f = open("AEP_list.txt", 'r')
            print "\033[96mConfirm AEP activation sequence provided in 'AEP_list.txt' ...\033[00m"
            i = 1
            for j in f.readlines():
                if j.strip().startswith("#") or j.strip() == "":
                    continue
                print " %s: %s" % (i, j.strip())
                i = i+1
            f.close()
            raw_input("Press enter to continue or CTRL+C to quit.")
            self.install_AEP()
        elif ch == '4':
            self.health_check_3()
        else:
            print ("\033[91mWrong Selection\033[00m")
            sys.exit(1)

    def get_tid_status(self, t):
        self.prPurple("[INFO]: Transaction ID generated: " + t)
        url = "https://{0}:28809/api/operational/sdl/state/derived-state/deployments/deployment/{1}/vnf-instances/" \
              "vnf-instance/{2}/operation/transactions/transaction/{3}?deep".format(self.confd_vip, self.lsdl,
                                                                                    self.sdli, t)
        headers = {'Accept': 'application/vnd.yang.data+json', }
        while True:
            sleep(15)
            res, code = self.get_output(url=url, headers=headers)
            self.http_status(code)
            stat = res['nokia-sdl:transaction']['status']
            if stat == "FAILED":
                self.prRed("[FAIL]: Execution failed for transaction-id: " + t)
                self.exit1()
            elif stat == "SUCCESS":
                self.prGreen("[PASS]: Execution successful for transaction-id: " + t)
                try:
                    self.ref = res['nokia-sdl:transaction']['ref']
                except:
                    pass
                break
            else:
                print "Execution in progress..."
                continue

    def http_status(self, code):
        if code == 401:
            self.prRed("[FAIL]: 401 - Authentication failure. Please check 'sdladmin' password.")
            self.exit1()
        elif code == 404:
            self.prPurple("[FAIL]: No output received from server. Error 404 - Not Found")
            self.exit1()
        elif code != 200:
            self.prRed("[FAIL]: HTTP return Code = " + str(code))
            self.exit1()

    def install_AEP(self):
        f = open(self.input_file, 'r')
        self.logs = open("/tmp/AEP/AEP_installation_{}.txt".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
        self.get_AEPs()
        self.prGreen("[INFO]: Starting AEP installation/activation...")
        for aep in f.readlines():
            aep = aep.strip()
            if aep.startswith("#") or aep == "":
                continue
            self.prheader()
            self.prBlue("[INFO]: Installing %s on %s : %s" % (aep, self.lsdl, self.sdli))
            n = aep.split("SDL-")[1].split("-")[0]
            v = aep.split(n + "-")[1].split("-W")[0]
            print >> self.logs, ("\033[95m[INFO]: Verifying if {0} is already installed or not...\033[00m".format(aep))
            # self.prPurple("[INFO]: Verifying if %s is already installed or not..." % aep)
            s, c = self.get_AEP_status(n, v)
            if c != 404:
                self.http_status(c)
                if s == "ACTIVATED":
                    self.prGreen("[PASS]: %s is already activated" % aep)
                    continue
                else:
                    self.prPurple("[WARN]: %s is in %s state." % (aep, s))
            self.load_exp(aep=aep, n=n, v=v)
            self.prepare_exp(aep=aep, n=n, v=v)
            self.activate_exp(aep=aep, n=n, v=v)
            self.prYellow("[INFO]: Verifying activation status of %s" % aep)
            while True:
                sleep(10)
                s, c = self.get_AEP_status(n, v)
                self.http_status(c)
                if s == "ACTIVATED":
                    self.prGreen("[PASS]: %s is activated successfully" % aep)
                    break
                elif s == "DEACTIVATED":
                    print "Execution in progress. Please wait..."
                    continue
                else:
                    self.prPurple("[FAIL]: Execution failed. %s is in %s state." % (aep, s))
                    self.exit1()
        self.get_AEPs()
        self.logs.close()
        f.close()

    def load_exp(self, aep, n, v):
        self.prCyan("[INFO]: Loading AEP - %s" % aep)
        self.aep_activity(act="load", n=n, v=v)
        self.prGreen("[PASS]: AEP load successful for %s" % aep)

    def prepare_exp(self, aep, n, v):
        self.prCyan("[INFO]: Preparing AEP - %s" % aep)
        self.aep_activity(act="prepare", n=n, v=v)
        self.prGreen("[PASS]: AEP preparation successful for %s" % aep)

    def activate_exp(self, aep, n, v):
        self.prCyan("[INFO]: Activating AEP - %s" % aep)
        self.aep_activity(act="activate", n=n, v=v)
        self.prGreen("[PASS]: AEP activation successful for %s" % aep)

    def aep_activity(self, act, n, v):
        # time.sleep(5)
        headers = {'Content-Type': 'application/vnd.yang.data+json', }
        data = '{"%s-exp":{"extension-packages":[{"name":"%s","version":"%s"}]}}' % (act, n, v)
        response = requests.post('https://{0}:28809/api/operations/sdl:{1}-exp'.format(self.confd_vip, act),
                                 headers=headers, data=data, verify=False, auth=('sdladmin', self.sdl_pass))
        code = response.status_code
        response = response.json()
        pretty_data = json.dumps(response, indent=4)
        self.prlogonly(pretty_data)
        self.http_status(code)
        t_id = response["nokia-sdl:output"]["transaction-id"]
        self.get_tid_status(t_id)

    def get_AEP_status(self, n, v):
        url = "https://{0}:28809/api/operational/sdl/state/derived-state/deployments/deployment/{1}/extensions/" \
              "extension-packages/{2},{3}/status".format(self.confd_vip, self.lsdl, n.lower(), v)
        headers = {'Accept': 'application/vnd.yang.data+json', }
        res, code = self.get_output(url=url, headers=headers)
        try:
            stat = res["nokia-sdl:status"]
        except:
            stat = ""
        return stat, code

    def get_output(self, url, headers):
        self.prYellow("[URL]        : %s" % url)
        self.prYellow("[Headers]    : %s" % headers)
        res = requests.get(url=url, headers=headers, verify=False, auth=('sdladmin', self.sdl_pass))
        code = res.status_code
        try:
            res = res.json()
            pretty_data = json.dumps(res, indent=4)
            self.prlogonly(pretty_data)
        except:
            self.prYellow("[Return Code]: %s" % code)
        return res, code

    def post_output(self, url, headers):
        self.prYellow("[URL]        : %s" % url)
        self.prYellow("[Headers]    : %s" % headers)
        res = requests.post(url=url, headers=headers, verify=False, auth=('sdladmin', self.sdl_pass))
        code = res.status_code
        self.prYellow("[Return Code]: %s" % code)
        res = res.json()
        pretty_data = json.dumps(res, indent=4)
        self.prlogonly(pretty_data)
        return res, code

    def get_AEPs(self):
        self.prPurple("[INFO]: Fetching current AEP status...")
        url = "https://{0}:28809/api/operational/sdl/state/derived-state/deployments/deployment/" \
              "{1}/extensions?deep".format(self.confd_vip, self.lsdl)
        headers = {'Accept': 'application/vnd.yang.data+json', }
        res, code = self.get_output(url=url, headers=headers)
        self.http_status(code)
        t = PrettyTable(['Name', 'Version', 'Status'])
        for i in res['nokia-sdl:extensions']['extension-packages']:
            t.add_row([i['name'], i['version'], i['status']])
        self.prPurple("[INFO]: ### Summary")
        self.prCyan(t)
        self.prCyan("\n")

    def de_activate_AEP(self):
        f = open(self.input_file, 'r')
        self.logs = open("/tmp/AEP/AEP_deactivation_{}.txt".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
        self.get_AEPs()
        self.prGreen("[INFO]: Starting AEP de-activation...")
        for aep in f.readlines():
            aep = aep.strip()
            if aep.startswith("#") or aep == "":
                continue
            self.prheader()
            self.prBlue("[INFO]: De-Activating %s on %s : %s" % (aep, self.lsdl, self.sdli))
            n = aep.split("SDL-")[1].split("-")[0]
            v = aep.split(n + "-")[1].split("-W")[0]
            self.prYellow("[INFO]: Verifying current status of %s" % aep)
            s, c = self.get_AEP_status(n, v)
            self.http_status(c)
            if s == "DEACTIVATED":
                self.prGreen("[PASS]: %s is already de-activated" % aep)
                continue
            else:
                self.prPurple("[WARN]: %s is in %s state." % (aep, s))
            self.aep_activity(act="deactivate", n=n, v=v)
            self.prGreen("[PASS]: AEP De-Activation successful for %s" % aep)
            self.prYellow("[INFO]: Verifying current status of %s" % aep)
            while True:
                sleep(10)
                s, c = self.get_AEP_status(n, v)
                self.http_status(c)
                if s == "DEACTIVATED":
                    self.prGreen("[PASS]: %s is de-activated successfully" % aep)
                    break
                elif s == "ACTIVATED":
                    print "Execution in progress. Please wait..."
                    continue
                else:
                    self.prPurple("[WARN]: %s is in %s state." % (aep, s))
                    self.exit1()
        self.get_AEPs()
        self.logs.close()
        f.close()

    def ftp_AEP(self):
        pass

    def exit1(self):
        print "\033[93m[LOGS]: Refer logs --> {}\033[00m".format(self.logs.name)
        self.logs.close()
        sys.exit(1)

    def health_check_SDL(self):
        self.logs = open("/tmp/AEP/AEP_HC_{}.txt".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
        self.prGreen("[INFO]: Initiating health check of SDL...")
        url = "https://{}:28809/api/operations/vnf-health-check".format(self.confd_vip)
        header = {'Content-Type': 'application/vnd.yang.data+json', }
        res, code = self.post_output(url=url, headers=header)
        self.http_status(code)
        t_id = res["nokia-sdl:output"]["transaction-id"]
        self.get_tid_status(t_id)
        rn = self.ref.split("/")[-1]
        self.prBlue("[INFO]: Fetching Health check file '%s' to local system" % rn)
        # cmd = "/usr/bin/expect -c 'spawn -noecho sftp -o StrictHostKeyChecking=no " \
        #       "sdladmin@[{0}]:/var/SharedStorage/hc_reports/{1}; expect \"*assword:\"; " \
        #       "send {2}\r; expect eof;'".format(self.diag_vip, rn, self.sdl_pass)
        # s, o = commands.getstatusoutput(cmd)
        # for i in o.splitlines():
        #     self.prlogonly(i.strip())
        self.scp_hc_json(rn)
        rn = os.path.join("/tmp/AEP", rn)
        if os.path.isfile(rn):
            self.prGreen("[PASS]: Health check file copied to local system -> %s" % rn)
        else:
            self.prRed("[FAIL]: Not able to fetch Health check file '%s'" % os.path.basename(rn))
            self.exit1()
        x = json.load(open(rn, ))
        t = PrettyTable(['Instance', 'VNF Health', 'SDN', 'VM Health', 'VNF ID', 'OAM_EXT IP'])
        for i in x["SDL"]:
            t.add_row([i["sdn"], i["health"], '', '', '', ''])
            for z in sorted(i["vmInstances"], key=lambda j: j["sdn"]):
                t.add_row(['', '', z["sdn"].split('/')[-1], z["health"], z["vnfcId"], z["ipAddress"]["OAM_EXT"][0]])
            t.add_row(['', '', '', '', '', ''])
        self.prPurple("\n[INFO]: ### Health Check Summary")
        self.prCyan(t)
        self.prCyan("\n")
        self.logs.close()

    def scp_hc_json(self, rn):
        cmd = "sftp -o StrictHostKeyChecking=no sdladmin@[{0}]:/var/SharedStorage/hc_reports/{1} /tmp/AEP/".format(
            self.diag_vip, rn)
        child = pexpect.spawn(cmd)
        child.logfile = self.logs
        while True:
            ch = child.expect([u'assword:', pexpect.TIMEOUT, pexpect.EOF])
            if ch == 0:
                child.sendline(self.sdl_pass)
            elif ch == 1:
                continue
            elif ch == 2:
                break
        child.close()
        print >> self.logs, ("\n")

    def health_check_3(self):
        self.logs = open("/tmp/AEP/AEP_HC_level3_{}.txt".format(dtm.now().strftime("%Y%m%d_%H%M%S")), 'w')
        self.prGreen("[INFO]: Initiating level 3 health check of SDL...")
        print("This will take a minute. Please wait...")
        cmd = "python /opt/nokia/sdl-operations/oes/scripts/get_health_check_report.py --hc_details level3 " \
              "--timeout 300 --alert_rule_name default"
        child = pexpect.spawn("su -")
        # child.logfile = self.logs
        child.expect("assword:")
        child.sendline(self.sdl_pass)
        child.logfile = self.logs
        child.expect("~]#")
        child.sendline(cmd)
        child.expect("assword:")
        child.sendline(self.sdl_pass)
        while True:
            ch = child.expect([pexpect.TIMEOUT, pexpect.EOF, "~]#"])
            if ch == 0:
                continue
            elif ch == 1:
                break
            elif ch == 2:
                child.sendline("exit")
                break
        rr = child.before
        child.expect(pexpect.EOF)
        child.close()
        try:
            # rn = l.split("/")[-1].split('"')[0] for l in rr.splitlines() if "sftp" in l else self.exit1()
            for l in rr.splitlines():
                if "sftp" in l:
                    rn = l.split("/")[-1].split('"')[0]
            self.prBlue("[INFO]: Fetching Health check file '%s' to local system" % rn)
        except:
            self.prRed("[FAIL]: Execution failed. Check log file")
            self.exit1()
        self.scp_hc_json(rn)
        rn = os.path.join("/tmp/AEP", rn)
        if os.path.isfile(rn):
            self.prGreen("[PASS]: Health check file copied to local system -> %s" % rn)
        else:
            self.prRed("[FAIL]: Not able to fetch Health check file '%s'" % os.path.basename(rn))
            self.exit1()
        x = json.load(open(rn, ))
        t = PrettyTable(['Instance', 'VNF Health', 'SDN/VM', 'Attribute', 'Response'])
        t.align["Attribute"] = "l"
        t.align["Response"] = "l"
        # status = x["health"]
        # print(status)
        for i in x["SDL"]:
            # print i
            t.add_row([i["sdn"], i["health"], '', '', ''])
            for y in sorted(i["vmInstances"], key=lambda j: j["ipAddress"]["OAM_EXT"][0]):
                t.add_row(['', '', y["sdn"].split('/')[-1], '-' * 15, '-' * 20])
                data = {'1. VM Health': y['health'], '2. VNFC Id': y['vnfcId'],
                        '3. OAM_EXT_IP': y["ipAddress"]["OAM_EXT"][0]}
                for alarm in y["alarms"]:
                    data['4. Alarm Code'] = alarm["alarmCode"]
                    data['5. Alarm Text'] = alarm["additionalText"]
                    data['6. Alarm Severity'] = alarm["alarmSeverity"]
                for sensor in y["sensors"]["brm"]:
                    name = sensor["name"]
                    if len(sensor["MOs"]) == 1:
                        data[name] = sensor["MOs"][0].split()[-1]
                    else:
                        data[name] = [(c.split()[0].split("\\")[-1].encode("UTF-8"), c.split()[-1].encode("UTF-8")) for
                                      c in
                                      sensor["MOs"]]

                for key in sorted(data.keys()):
                    t.add_row(['', '', '', key, data[key]])
        self.prPurple("\n[INFO]: ### Health Check Summary (Level 3)")
        self.prCyan(t)
        self.prCyan("\n")
        self.logs.close()

    def get_tpd(self):
        print "\033[93m[INFO]: Fetching details from '/sdlinst/TPD.yaml'. " \
              "Please enter root user password, if prompts for.\033[00m"
        s, out = commands.getstatusoutput("sudo cat /sdlinst/TPD.yaml")
        tpd = yaml.load(out)
        par = {"sld_i": tpd['application-parameters']['sdl-instance'],
               "lsdl_i": tpd['application-parameters']['lsdl-instance']}
        # print tpd['root_passwd']
        # print tpd['sdladmin_passwd']
        try:
            par["diag_vip"] = tpd['networks']['ext-oam-network']['ipv6']['diag_vip_ipv4']
            par["confd_vip"] = tpd['networks']['ext-oam-network']['ipv6']['confd_vip_ipv4']
            par["ops_vm"] = tpd['networks']['ext-oam-network']['ipv6']['ops']
        except KeyError:
            par["diag_vip"] = tpd['networks']['ext-oam-network']['ipv4']['diag_vip_ipv4']
            par["confd_vip"] = tpd['networks']['ext-oam-network']['ipv4']['confd_vip_ipv4']
            par["ops_vm"] = tpd['networks']['ext-oam-network']['ipv4']['ops']
        except:
            raise
        # raw_input("Press Enter to continue...")
        sdl_pass = raw_input("Enter 'sdladmin' user password: ")
        par["sdl_pass"] = sdl_pass.strip()
        return par

    def prRed(self, msg):
        print ("\033[91m{}\033[00m".format(msg))
        print >> self.logs, ("\033[91m{}\033[00m".format(msg))

    def prGreen(self, msg):
        print ("\033[92m{}\033[00m".format(msg))
        print >> self.logs, ("\033[92m{}\033[00m".format(msg))

    def prYellow(self, msg):
        # print ("\033[93m{}\033[00m".format(msg))
        print >> self.logs, ("\033[93m{}\033[00m".format(msg))

    def prBlue(self, msg):
        print("\033[94m{}\033[00m".format(msg))
        print >> self.logs, ("\033[94m{}\033[00m".format(msg))

    def prPurple(self, msg):
        print("\033[95m{}\033[00m".format(msg))
        print >> self.logs, ("\033[95m{}\033[00m".format(msg))

    def prCyan(self, msg):
        print("\033[96m{}\033[00m".format(msg))
        print >> self.logs, ("\033[96m{}\033[00m".format(msg))

    def prborder(self):
        print "-" * 70
        print >> self.logs, "-" * 70

    def prheader(self):
        print "=" * 70
        print >> self.logs, "\n"
        print >> self.logs, "=" * 70
        print >> self.logs, "\n"

    def prlogonly(self, text):
        print >> self.logs, (text.encode('utf-8'))

def sub_menu2(sel):
    os.system('clear')
    if sel:
        print "\033[91mInvalid selection.\033[00m"
    print "="*80
    print("\033[95mWelcome to AEP Installation Tool v2.0\033[00m".center(80))
    print "=" * 80
    print("\033[93m 1. SDL Health check\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 2. Current AEP status\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 3. AEP activation\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 4. SDL Health Check - Level 3\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 9. Back to Main Menu\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 0. Quit\033[00m".ljust(80))
    print "=" * 80
    print ""
    choice = raw_input("YOUR SELECTION: >> ")
    choice = choice.strip()
    if choice == '0':
        sys.exit()
    elif choice == '9':
        main_menu(sel=False)
        sys.exit()
    elif choice not in ['1', '2', '3', '4']:
        choice = sub_menu2(sel=True)
    else:
        AEP(ch=choice)
        return
    return choice


def sub_menu1(sel):
    os.system('clear')
    if sel:
        print "\033[91mInvalid selection.\033[00m"
    print "=" * 80
    print("\033[95mWelcome to SDL Toolkit v22.0\033[00m".center(80))
    print "=" * 80
    print("\033[93m 1. VNF input preparation\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 2. SDL terminate\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 3. SDL check instantiate\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 9. Back to Main Menu\033[00m".ljust(80))
    print "-" * 80
    print("\033[93m 0. Quit\033[00m".ljust(80))
    print "=" * 80
    print ""
    choice = raw_input("YOUR SELECTION: >> ")
    choice = choice.strip()
    if choice == '0':
        sys.exit()
    elif choice == '9':
        main_menu(sel=False)
        sys.exit()
    elif choice not in ['1', '2', '3']:
        choice = sub_menu1(sel=True)
    else:
        SDL(c=choice)
        return
    return choice


def main_menu(sel):
    os.system('clear')
    if sel:
        print "\033[91mInvalid selection.\033[00m"
    print "="*80
    print("\033[95mWelcome to SDL Toolkit v22.0\033[00m".center(80))
    print "=" * 80
    print("\033[93m 1. SDL Preparation, Instantiation and Termination\033[00m".ljust(80))
    print "-" * 80 
    print("\033[93m 2. SDL Health Check and AEP Management\033[00m".ljust(80))
    print "-" * 80
    #print("\033[93m 3. SDL Post Check and Configurations\033[00m".ljust(80))
    #print "-" * 80 
    print("\033[93m 0. Quit\033[00m".ljust(80))
    print "=" * 80
    print ""
    choice = raw_input("YOUR SELECTION: >> ")
    choice = choice.strip()
    if choice == '0':
        sys.exit()
    elif choice == '1':
        sub_menu1(sel=False)
    elif choice == '2':
        sub_menu2(sel=False)
    else:
        main_menu(sel=True)
    # return choice


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print "\033[91mInvalid Usage\033[00m"
        print "\033[93mUsage        : ./{0} or python {0}".format(sys.argv[0])
        print ""
        sys.exit(1)
    # in_file = sys.argv[1]
    # if not os.path.isfile(in_file):
    #     print "\033[91m[FAIL]: File not found. Check file '%s'\n\033[00m" % in_file
    #     sys.exit(1)
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    while True:
        main_menu(sel=False)
        raw_input("Press Enter to continue...")
