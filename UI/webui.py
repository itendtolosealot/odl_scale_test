from flask import Flask, flash, redirect, render_template, request, session, abort
from logging.config import dictConfig

class WebUIForSimulator():
    DEBUG=True
    def __init__(self, simulator):
        self._request_handler = simulator

    def run(self, ip, port):
        LOGGING_CONFIG = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'handlers': {
                'default': {
                    'level': 'DEBUG',
                    'formatter': 'standard',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': '/home/stack/mininet_handler/webui.log',  # Default is stderr
                    'maxBytes': '1024000',
                    'backupCount': '2',
                },
            },
            'loggers': {
                '': {  # root logger
                    'handlers': ['default'],
                    'level': 'DEBUG',
                    'propagate': False
                }
            }
        }
        dictConfig(LOGGING_CONFIG)
        app = Flask('WebUIForSimulator', template_folder='./UI/templates', static_folder='./UI/static/')

        @app.route('/deploy')
        def deploy():
            return render_template('deploy.html', host_ip=ip, host_port=port)

        @app.route('/result', methods = ['POST', 'GET'])
        def result():
            test_manage_keys = ["activate", "deactivate"]
            compute_manage_keys = ["deploy_computes", "destroy_computes", "status_computes"]
            if request.method == 'POST':
                result = request.form
                args = request.args
                app.logger.info("Args from the POST: " + str(args))
                result_keys = result.keys()
                if set(compute_manage_keys).intersection(result_keys) != set():
                    if("deploy_computes" in result_keys):
                        command = "start"
                        app.logger.info("Deploying the Compute Containers")
                    elif ("destroy_computes" in result_keys):
                        command = "stop"
                        app.logger.info("Destroying the Compute Containers")
                    else:
                        command = "status"
                        app.logger.info("Status of Compute containers")
                    response=self._request_handler.handle_switch_creation(command, result["controller_ip"],int(result["num_computes_range"]))
                elif set(test_manage_keys).intersection(result_keys) !=set():
                    app.logger.info("Enabling Testing of Resources")
                    if("activate" in result_keys):
                        command = "start"
                    else:
                        command="stop"
                    for resource in result_keys():
                        if(not (resource == "activate" or resource=="deactivate")):
                            response = self._request_handler.handle_test(resource, command)
                return render_template("result.html",result = result, response=response, title="Status of OF/OVSDB Connection")

        @app.route('/test')
        def test():
            return render_template('test.html')

        @app.route('/mip')
        def mip():
            return render_template('mip.html')

        @app.route('/config')
        def config():
            config = self._request_handler.get_running_config()
            return render_template('config.html', config=config)

        @app.route('/')
        def index():
            return config()

        app.logger.info("Inside the WebUI. Starting the application...")
        try:
            app.run(host=ip, port=port)
        except Exception as ex:
            app.logger.error("Encountered exception: " + str(ex.message))

