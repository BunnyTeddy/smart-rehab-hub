"""Create a preregistered doctor; no email is sent and no existing account is reset."""
import argparse
from pathlib import Path
import re
from .admin import Admin


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',args.email) or not 1<=len(args.name.strip())<=100:
        raise SystemExit('Supply a valid email and doctor display name')
    filename=re.sub(r'[^a-z0-9_-]','_',args.email.lower())
    path=Path.home()/'.config/smart-rehab/doctors'/(filename+'.json')
    admin=Admin()
    account=admin.new_account(args.email,args.name.strip(),{'role':'doctor'},path)
    admin.database('rehab_v1/doctorDirectory/'+account['uid'],'PUT',{'name':args.name.strip()})
    print('Doctor account provisioned. Deliver the initial password privately from: '+str(path))


if __name__=='__main__':main()
