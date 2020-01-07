from keystoneauth1 import identity
from keystoneauth1 import session
from neutronclient.v2_0 import client
username='admin'
password='password'
project_name='demo'
project_domain_id='default'
user_domain_id='default'
auth_url='http://10.128.128.103/identity'
auth = identity.Password(auth_url=auth_url,username=username,password=password,project_name=project_name,project_domain_id=project_domain_id, user_domain_id=user_domain_id)
sess = session.Session(auth=auth)
neutron = client.Client(session=sess)