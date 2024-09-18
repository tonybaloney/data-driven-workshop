html:
	cd src/html; npx tailwindcss -i input.css -o css/output.css

runserver:
	npx http-server src/html --proxy http://localhost:7071 &
	cd src/api ; func host start -
