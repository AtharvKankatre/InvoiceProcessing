# create python virtual environment
python3 -m venv venv

# activete virtual environment
linux: source venv/bin/activate
windows: .\venv\activate

# install required packages
pip install -r requirements.txt

# set environment variables
make copy of env.template file <br>
rename the copied file to .env <br>
replace placeholder values with actual values

# run django migrations
python manage.py migrate

# create an admin user
python manage.py createsuperuser <br>
fill in the details for admin user

# run server
python manage.py runserver