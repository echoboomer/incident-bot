import { React, useState } from 'react';
import { useSpring, animated, easings } from 'react-spring';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  FilledInput,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  Snackbar,
  Typography
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { lightBlue } from '@mui/material/colors';
//import HiveRoundedIcon from '@mui/icons-material/HiveRounded';
import LoginIcon from '@mui/icons-material/Login';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import PropTypes from 'prop-types';
import { apiUrl } from '../shared/Variables';
import logo from '../img/logo.png';
import Move from '../shared/Move';

async function loginUser(credentials) {
  return fetch(`${apiUrl}/user/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(credentials)
  }).then((data) => data.json());
}

const LoginPage = ({ setToken }) => {
  const [values, setValues] = useState({
    email: '',
    password: ''
  });

  const handleChange = (prop) => (event) => {
    setValues({ ...values, [prop]: event.target.value });
  };

  const handleClickShowPassword = () => {
    setValues({
      ...values,
      showPassword: !values.showPassword
    });
  };

  const handleMouseDownPassword = (event) => {
    event.preventDefault();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const token = await loginUser({
      email: `${values.email}`,
      password: `${values.password}`
    });
    if (!token.success) {
      setLoginMessage(token.error);
      setOpenLoginStatus(true);
    } else if (token.success) {
      setToken(token.access_token);
    }
  };

  const LoginButton = styled(Button)(({ theme }) => ({
    color: theme.palette.getContrastText(lightBlue[600]),
    backgroundColor: lightBlue[700],
    '&:hover': {
      backgroundColor: lightBlue[500]
    }
  }));

  const [loginMessage, setLoginMessage] = useState('');
  const [openLoginStatus, setOpenLoginStatus] = useState(false);

  function EasingComponent() {
    const { rotateZ } = useSpring({
      from: {
        rotateZ: 0
      },
      to: {
        rotateZ: 360
      },
      config: {
        duration: 2000,
        easing: easings.easeInOutQuart
      },
      loop: { reverse: true }
    });

    return (
      <animated.div style={{ width: 60, height: 60, borderRadius: 35, rotateZ }}>
        <center>
          <img src={logo} />
        </center>
      </animated.div>
    );
  }

  return (
    <div
      className="gradient-bg-blue"
      style={{
        height: '100vh'
      }}>
      <form onSubmit={handleSubmit}>
        <Grid
          container
          spacing={0}
          direction="column"
          alignItems="center"
          justifyContent="center"
          style={{ minHeight: '60vh' }}>
          <Grid item>
            <Card
              sx={{ minWidth: '35vh' }}
              style={{
                backgroundImage: 'linear-gradient(to right, #89CFF0, #01579B)'
              }}>
              <Box display="flex" justifyContent="center" sx={{ paddingBottom: 1, paddingTop: 8 }}>
                <EasingComponent />
              </Box>
              <Grid item>
                <Box
                  display="flex"
                  justifyContent="center"
                  alignItems="center"
                  sx={{ paddingBottom: 4, paddingTop: 1 }}>
                  <Typography
                    variant="h6"
                    sx={{
                      display: { xs: 'none', md: 'flex' },
                      fontFamily: 'Roboto',
                      fontWeight: 1000,
                      letterSpacing: '.6rem',
                      color: '#ffffff'
                    }}>
                    APIARY
                  </Typography>
                </Box>
              </Grid>
              <Grid item>
                <Box display="flex" justifyContent="center" alignItems="center">
                  <FormControl sx={{ m: 2, width: '30ch' }} variant="outlined">
                    <InputLabel htmlFor="email">Email</InputLabel>
                    <FilledInput
                      required
                      id="email"
                      type="email"
                      value={values.email}
                      onChange={handleChange('email')}
                      label="Email"
                    />
                  </FormControl>
                </Box>
                <Box display="flex" justifyContent="center" alignItems="center">
                  <FormControl sx={{ m: 2, width: '30ch' }} variant="outlined">
                    <InputLabel htmlFor="password">Password</InputLabel>
                    <FilledInput
                      required
                      id="password"
                      type={values.showPassword ? 'text' : 'password'}
                      value={values.password}
                      onChange={handleChange('password')}
                      endAdornment={
                        <InputAdornment position="end">
                          <IconButton
                            aria-label="toggle password visibility"
                            onClick={handleClickShowPassword}
                            onMouseDown={handleMouseDownPassword}
                            edge="end">
                            {values.showPassword ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      }
                      label="Password"
                    />
                  </FormControl>
                </Box>
                <Grid item>
                  <Box
                    display="flex"
                    justifyContent="center"
                    alignItem="center"
                    sx={{ paddingBottom: 2 }}>
                    <CardActions>
                      <FormControl>
                        <Move
                          rotation={0}
                          timing={1000}
                          scale={1.2}
                          springConfig={{ tension: 150, friction: 20 }}>
                          <LoginButton size="large" endIcon={<LoginIcon />} type="submit">
                            LOGIN
                          </LoginButton>
                        </Move>
                      </FormControl>
                    </CardActions>
                  </Box>
                </Grid>
              </Grid>
            </Card>
          </Grid>
        </Grid>
      </form>
      {openLoginStatus && (
        <Snackbar
          open={openLoginStatus}
          autoHideDuration={6000}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          onClose={(event, reason) => {
            if (reason === 'clickaway') {
              return;
            }
            setOpenLoginStatus(false);
          }}>
          <Alert severity="error" variant="filled" sx={{ width: '100%' }}>
            {loginMessage}
          </Alert>
        </Snackbar>
      )}
    </div>
  );
};

LoginPage.propTypes = {
  setToken: PropTypes.func.isRequired
};

export default LoginPage;
