from fabric.api import env, run, cd, local, sudo, settings, hosts, put

env.use_ssh_config = True


def update():
    run('mkdir -p /home/pi/coffee/')
    with cd('/home/pi/coffee/'):
        put('./coffee.py', '.')
        put('./requirements.txt', '.')

    sudo('systemctl restart coffeemachine.service')
    run('journalctl -f -u coffeemachine.service ')
