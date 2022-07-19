import Dashboard from './dashboard/View';
//import LoginPage from './components/Login.component';

//import useToken from './shared/useToken';

export default function App() {
  //const { token, setToken } = useToken();
  //if (!token) {
  //  return <LoginPage setToken={setToken} />;
  //}

  return (
    <div className="main">
      <div className="content-container">
        <Dashboard />
      </div>
    </div>
  );
}
