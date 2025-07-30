<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Crypto Filter Login</title>
  <style>
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      padding: 0;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #0d1b2a;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }
    .login-container {
      background-color: #1b263b;
      padding: 40px;
      border-radius: 16px;
      width: 360px;
      text-align: center;
      box-shadow: 0 0 20px rgba(0,0,0,0.3);
    }
    .login-container img {
      width: 100px;
      height: 100px;
      border-radius: 50%;
      margin-bottom: 20px;
    }
    .login-container h2 {
      color: #e0a96d;
      margin-bottom: 30px;
      font-size: 24px;
    }
    input[type="email"], input[type="password"] {
      width: 100%;
      padding: 12px;
      margin: 10px 0;
      border: none;
      border-radius: 8px;
      background-color: #415a77;
      color: white;
      font-size: 16px;
    }
    input::placeholder {
      color: #cbd5e1;
    }
    .login-btn {
      width: 100%;
      background-color: #e0a96d;
      color: #1b263b;
      border: none;
      padding: 12px;
      font-size: 16px;
      border-radius: 8px;
      cursor: pointer;
      margin-top: 20px;
      transition: background-color 0.3s ease;
    }
    .login-btn:hover {
      background-color: #f0bb7d;
    }
    .login-footer {
      margin-top: 20px;
      color: #cbd5e1;
    }
    .login-footer a {
      color: #f0bb7d;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <div class="login-container">
    <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAAAAAQACAIAAADwf7zUAAEAAElEQVR4nFx9y4IkSY4bQM+rdNVR+v" alt="Persian Cat Logo" />
    <h2>CRYPTO FILTER</h2>
    <input type="email" placeholder="Email Address" required />
    <input type="password" placeholder="Password" required />
    <button class="login-btn">Log In</button>
    <div class="login-footer">
      <p><a href="#">Forgot password?</a></p>
      <p>Don’t have an account? <a href="#">Sign up</a></p>
    </div>
  </div>
</body>
</html>
