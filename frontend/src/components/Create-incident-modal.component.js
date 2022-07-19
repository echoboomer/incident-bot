import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CircularProgress,
  Container,
  FormControl,
  Grid,
  Input,
  InputLabel,
  MenuItem,
  Modal,
  Select,
  Snackbar,
  Typography
} from '@mui/material';

import { styled } from '@mui/material/styles';
import { lightBlue } from '@mui/material/colors';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import LiveHelpIcon from '@mui/icons-material/LiveHelp';
import Move from '../shared/Move';

export default function IncidentCreateModal(props) {
  const [loadingData, setLoadingData] = useState(false);
  const [values, setValues] = useState({
    description: '',
    user: '',
    severity: ''
  });

  const handleChange = (prop) => (event) => {
    setValues({ ...values, [prop]: event.target.value });
    console.log(values);
  };

  const CreateIncidentButton = styled(Button)(({ theme }) => ({
    color: theme.palette.getContrastText(lightBlue[600]),
    backgroundColor: lightBlue[700],
    '&:hover': {
      backgroundColor: lightBlue[500]
    }
  }));

  const style = {
    position: 'absolute',
    top: '30%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 700,
    height: 700,
    p: 10
  };

  const [open, setOpen] = useState(false);
  const [firstLoad, setFirstLoad] = useState(false);
  const handleOpen = () => {
    setOpen(true), setFirstLoad(true);
  };
  const handleClose = () => setOpen(false);

  const [createIncidentStatus, setCreateIncidentStatus] = useState('');
  const [createIncidentMessage, setCreateIncidentMessage] = useState('');
  const [openCreateIncidentStatus, setOpenCreateIncidentStatus] = useState(false);

  async function createIncident(values) {
    console.log(values);
    return fetch(`${props.apiUrl}/incidents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(values)
    }).then((data) => data.json());
  }

  const handleSubmit = async (e) => {
    setLoadingData(true);
    e.preventDefault();
    const incident = await createIncident({
      description: `${values.description}`,
      user: `${values.user}`,
      severity: `${values.severity}`
    });
    if (!incident.success) {
      setCreateIncidentStatus('error');
      setCreateIncidentMessage(`Error creating incident: ${incident.error}`);
      setOpenCreateIncidentStatus(true);
    } else if (incident.success) {
      setCreateIncidentStatus('success');
      setCreateIncidentMessage('Incident created successfully!');
      setOpenCreateIncidentStatus(true);
      setOpen(false);
      window.location.reload();
    }
  };

  // Fetch users
  const [users, setUsers] = useState([]);

  function getSlackUsers() {
    var url = props.apiUrl + '/incidents/slack_users';
    axios({
      method: 'GET',
      responseType: 'json',
      url: url
    })
      .then(function (response) {
        setUsers(response.data.data);
      })
      .catch(function (error) {
        if (error.response) {
          console.log(error.response);
        } else if (error.request) {
          console.log(error.request);
        }
      });
  }

  // Retrieve users only when modal is opened
  useEffect(() => {
    if (open && firstLoad) getSlackUsers();
  }, [open, firstLoad]);

  return (
    <div>
      <Button
        onClick={handleOpen}
        variant="contained"
        endIcon={<AddIcon />}
        sx={{
          paddingLeft: 2,
          paddingRight: 2,
          marginLeft: 1,
          marginRight: 1,
          marginBottom: 1,
          marginTop: 1
        }}>
        New Incident
      </Button>
      <Modal
        open={open}
        onClose={handleClose}
        aria-labelledby="create-incident-modal-title"
        aria-describedby="create-incident-modal-description">
        <Box sx={style}>
          <form onSubmit={handleSubmit}>
            <Card raised sx={{ width: '45vh', height: '50vh' }}>
              <Move
                rotation={0}
                timing={1000}
                scale={1.2}
                springConfig={{ tension: 150, friction: 5 }}>
                <CloseIcon sx={{ m: 1 }} onClick={() => setOpen(false)} />
              </Move>
              <Box display="flex" justifyContent="center" sx={{ paddingBottom: 1, paddingTop: 2 }}>
                <LiveHelpIcon fontSize="large" />
              </Box>
              <Grid item>
                <Box display="flex" justifyContent="center" alignItems="center">
                  <Typography
                    variant="h6"
                    sx={{
                      display: { xs: 'none', md: 'flex' },
                      fontFamily: 'Roboto',
                      fontWeight: 1000,
                      letterSpacing: '.1rem'
                    }}>
                    Report Incident
                  </Typography>
                </Box>
                <Box display="flex" justifyContent="center" alignItems="center" sx={{ padding: 3 }}>
                  <p>
                    This will create a new incident via Slack. This is similar to using the{' '}
                    <b>create incident</b> modal directly in Slack. Select your name from the user
                    list below before submitting.
                  </p>
                </Box>
              </Grid>
              <Grid item>
                <Box display="flex" justifyContent="center" alignItems="center">
                  <FormControl sx={{ m: 1, width: '80%' }} variant="standard">
                    <InputLabel htmlFor="description">Description</InputLabel>
                    <Input
                      required
                      id="description"
                      type="text"
                      value={values.description}
                      onChange={handleChange('description')}
                      label="Description"
                    />
                  </FormControl>
                </Box>
                <Grid item>
                  <Box display="flex" justifyContent="center" alignItem="center">
                    <FormControl sx={{ m: 1, width: '80%' }} variant="standard">
                      <InputLabel id="user">User</InputLabel>
                      <Select
                        required
                        labelId="user"
                        id="user"
                        value={values.user}
                        label="User"
                        onChange={handleChange('user')}>
                        {users.map((user) => [
                          <MenuItem value={user.id} key={user.name}>
                            {user.name}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>
                  </Box>
                </Grid>
                <Grid item>
                  <Box display="flex" justifyContent="center" alignItem="center">
                    <FormControl sx={{ m: 1, width: '80%' }} variant="standard">
                      <InputLabel id="severity">Severity</InputLabel>
                      <Select
                        required
                        labelId="severity"
                        id="severity"
                        value={values.severity}
                        label="Severity"
                        onChange={handleChange('severity')}>
                        {props.severities.map((sev) => [
                          <MenuItem value={sev} key={sev}>
                            {sev.toUpperCase()}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>
                  </Box>
                </Grid>
                <Grid item>
                  <Box
                    display="flex"
                    justifyContent="center"
                    alignItem="center"
                    sx={{ paddingTop: 2 }}>
                    <CardActions>
                      <FormControl>
                        {loadingData ? (
                          <CircularProgress />
                        ) : (
                          <Move
                            rotation={0}
                            timing={1000}
                            scale={1.05}
                            springConfig={{ tension: 150, friction: 5 }}>
                            <CreateIncidentButton
                              size="large"
                              endIcon={<AddCircleOutlineIcon />}
                              type="submit">
                              CREATE
                            </CreateIncidentButton>
                          </Move>
                        )}
                      </FormControl>
                    </CardActions>
                  </Box>
                </Grid>
              </Grid>
            </Card>
          </form>
        </Box>
      </Modal>
      {createIncidentStatus && (
        <Container>
          <Snackbar
            open={openCreateIncidentStatus}
            autoHideDuration={6000}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            onClose={(event, reason) => {
              if (reason === 'clickaway') {
                return;
              }
              setOpenCreateIncidentStatus(false);
            }}>
            <Alert
              severity={createIncidentStatus ? createIncidentStatus : 'info'}
              variant="filled"
              sx={{ width: '100%' }}>
              {createIncidentMessage}
            </Alert>
          </Snackbar>
        </Container>
      )}
    </div>
  );
}
