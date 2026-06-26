from app import app

# Vercel will import this module and use the `app` object as the WSGI entrypoint.

if __name__ == '__main__':
    app.run()
