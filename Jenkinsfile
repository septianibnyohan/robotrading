pipeline {
    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Setup Environment') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            python3 -m venv venv
                            venv/bin/python -m pip install --upgrade pip
                        '''
                    } else {
                        bat '''
                            @echo off
                            set "PY_PATH="
                            if exist "C:\\Users\\septi\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" set "PY_PATH=C:\\Users\\septi\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
                            if exist "C:\\Users\\septian\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" set "PY_PATH=C:\\Users\\septian\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
                            where python >nul 2>nul
                            if %ERRORLEVEL% equ 0 if not defined PY_PATH set "PY_PATH=python"
                            
                            if not defined PY_PATH (
                                echo ERROR: python.exe not found on Jenkins host.
                                exit /b 1
                            )
                            
                            echo Using Python executable: %PY_PATH%
                            "%PY_PATH%" -m venv venv
                            venv\\Scripts\\python.exe -m pip install --upgrade pip
                        '''
                    }
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'venv/bin/pip install -r requirements.txt'
                    } else {
                        bat 'venv\\Scripts\\pip install -r requirements.txt'
                    }
                }
            }
        }

        stage('Lint') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            if [ -f venv/bin/ruff ]; then
                                venv/bin/ruff check --exit-zero .
                            else
                                echo "Ruff not installed, skipping lint check."
                            fi
                        '''
                    } else {
                        bat '''
                            if exist venv\\Scripts\\ruff.exe (
                                venv\\Scripts\\ruff check --exit-zero .
                            ) else (
                                echo Ruff not installed, skipping lint check.
                            )
                        '''
                    }
                }
            }
        }

        stage('Test') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            mkdir -p reports
                            venv/bin/pytest --junitxml=reports/junit.xml
                        '''
                    } else {
                        bat '''
                            if not exist reports mkdir reports
                            venv\\Scripts\\pytest --junitxml=reports/junit.xml
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Please inspect logs and test reports.'
        }
    }
}
