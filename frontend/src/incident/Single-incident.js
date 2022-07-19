import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import {
  Alert,
  Box,
  Breadcrumbs,
  Card,
  CardHeader,
  CircularProgress,
  Chip,
  Container,
  Divider,
  FormControl,
  InputLabel,
  LinearProgress,
  Link,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Typography
} from '@mui/material';
import { apiUrl } from '../shared/Variables';

import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AnnouncementIcon from '@mui/icons-material/Announcement';
import DeveloperBoardIcon from '@mui/icons-material/DeveloperBoard';
import DoNotDisturbOnIcon from '@mui/icons-material/DoNotDisturbOn';
import FindReplaceIcon from '@mui/icons-material/FindReplace';
import ForumIcon from '@mui/icons-material/Forum';
import LabelIcon from '@mui/icons-material/Label';
import MilitaryTechIcon from '@mui/icons-material/MilitaryTech';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import PeopleIcon from '@mui/icons-material/People';
import UpdateIcon from '@mui/icons-material/Update';
import WarningIcon from '@mui/icons-material/Warning';

import AuditLogTable from './Audit-log-table.component';
import { severities, statuses } from '../shared/Variables';
import { acGradientPerTheme } from '../shared/setTheme';

const ViewSingleIncident = () => {
  const { incidentName } = useParams();

  const [incident, setIncident] = useState();
  const [auditLogData, setAuditLogData] = useState();
  const [users, setUsers] = useState([]);
  const [loadingData, setLoadingData] = useState(true);
  const [refreshData, setRefreshData] = useState(false);
  const [waitingForSomething, setWaitingForSomething] = useState(false);

  const [fetchStatus, setFetchStatus] = useState('');
  const [fetchMessage, setFetchMessage] = useState('');
  const [openFetchStatus, setOpenFetchStatus] = useState(false);

  const [values, setValues] = useState({
    channel_id: '',
    role: '',
    bp_message_ts: '',
    user: ''
  });

  // Backend API Functions
  function getSingleIncident() {
    axios({
      method: 'GET',
      responseType: 'json',
      url: apiUrl + '/incidents/' + incidentName
    })
      .then(function (response) {
        setIncident(response.data.data);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving incident from backend: ${error.response.data.error}`);
          setOpenFetchStatus(true);
        } else if (error.request) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving incidents from backend: ${error}`);
          setOpenFetchStatus(true);
        }
      });
  }

  function getIncidentAuditLog() {
    var url = apiUrl + '/incidents/' + incidentName + '/audit';
    axios({
      method: 'GET',
      responseType: 'json',
      url: url
    })
      .then(function (response) {
        setAuditLogData(response.data.data);
        setLoadingData(false);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving audit log from backend: ${error.response.data.error}`);
          setOpenFetchStatus(true);
        } else if (error.request) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving audit log from backend: ${error.response.data.error}`);
          setOpenFetchStatus(true);
        }
      });
  }

  function getSlackUsers() {
    var url = apiUrl + '/incidents/slack_users';
    axios({
      method: 'GET',
      responseType: 'json',
      url: url
    })
      .then(function (response) {
        setUsers(response.data.data);
        setLoadingData(false);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving users from backend: ${error.response.data.error}`);
          setOpenFetchStatus(true);
        } else if (error.request) {
          setFetchStatus('error');
          setFetchMessage(`Error retrieving users from backend: ${error}`);
          setOpenFetchStatus(true);
        }
      });
  }

  function updateIncidentRole(incidentID) {
    var url = apiUrl + '/incidents/' + incidentID + '/role';
    setWaitingForSomething(true);
    axios({
      method: 'POST',
      url: url,
      data: JSON.stringify(values),
      headers: { 'Content-Type': 'application/json' }
    })
      .then(function () {
        setFetchStatus('success');
        setFetchMessage(`Successfully updated incident.`);
        setWaitingForSomething(false);
        setOpenFetchStatus(true);
        setRefreshData(true);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchStatus('error');
          setFetchMessage(`Error updating user: ${error.response.data.error}`);
          setOpenFetchStatus(true);
          setWaitingForSomething(false);
        } else if (error.request) {
          setFetchStatus('error');
          setFetchMessage(`Error updating user: ${error}`);
          setOpenFetchStatus(true);
          setWaitingForSomething(false);
        }
      });
  }

  // Handlers
  const handleUserAssign = (props) => (event) => {
    values.channel_id = props.channelID;
    values.role = props.role;
    values.bp_message_ts = props.messageTS;
    // The request to Slack has to be user ID, not name
    // Names make more sense in presentation
    let userID;
    users.forEach((obj) => {
      if (obj.name === event.target.value) {
        userID = obj.id;
      }
    });
    values.user = userID;
    setValues({ ...values });
    updateIncidentRole(props.incidentID);
  };

  // Retrieve incidents and users
  useEffect(() => {
    getSingleIncident();
    getIncidentAuditLog();
    getSlackUsers();
  }, []);

  if (refreshData) {
    setRefreshData(false);
    getSingleIncident();
    getIncidentAuditLog();
    getSlackUsers();
  }

  return (
    <div className="view-single-incident-page">
      {!loadingData ? (
        <Container sx={{ paddingTop: 5 }}>
          {incident !== undefined ? (
            <>
              <Breadcrumbs
                aria-label="breadcrumb"
                separator={<NavigateNextIcon fontSize="small" />}
                sx={{ paddingBottom: 2 }}>
                <Link
                  underline="hover"
                  sx={{ display: 'flex', alignItems: 'center' }}
                  color="inherit"
                  href="/app/incidents">
                  <AnnouncementIcon sx={{ mr: 0.5 }} fontSize="inherit" />
                  Incidents
                </Link>
                <Typography sx={{ display: 'flex', alignItems: 'center' }} color="text.primary">
                  {incident.incident_id}
                </Typography>
              </Breadcrumbs>

              <Card>
                <CardHeader
                  avatar={<AnnouncementIcon sx={{ marginRight: 1 }} />}
                  title={`Details`}
                  style={{
                    backgroundImage: acGradientPerTheme
                  }}
                />
                <List
                  sx={{
                    width: '100%'
                  }}>
                  {incident.status === 'resolved' && (
                    <Alert severity="info">
                      This incident has been marked as resolved and it cannot be reopened. If there
                      is a new issue, please create a new incident.
                    </Alert>
                  )}
                  <ListItem dense key="created_at">
                    <ListItemIcon>
                      <AccessTimeIcon fontSize="large" />
                    </ListItemIcon>
                    <ListItemText primary="Created" secondary={`${incident.created_at}`} />
                  </ListItem>
                  <ListItem dense key="updated_at">
                    <ListItemIcon>
                      <UpdateIcon fontSize="large" />
                    </ListItemIcon>
                    <ListItemText primary="Last Update" secondary={`${incident.updated_at}`} />
                  </ListItem>

                  <ListItem dense key="status">
                    <ListItemIcon>
                      <FindReplaceIcon fontSize="large" />
                    </ListItemIcon>
                    <FormControl variant="standard" size="small" sx={{ m: 1, minWidth: 120 }}>
                      <InputLabel id="severity-select">Severity</InputLabel>
                      <Select
                        labelId="severity-select"
                        id="severity-select"
                        value={incident.status}
                        disabled={waitingForSomething || incident.status === 'resolved'}
                        onChange={() => console.log('changed')}>
                        {statuses.map((status) => [
                          <MenuItem value={status} key={status}>
                            {status}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>
                  </ListItem>

                  <ListItem dense key="severity">
                    <ListItemIcon>
                      <WarningIcon fontSize="large" />
                    </ListItemIcon>
                    <FormControl variant="standard" size="small" sx={{ m: 1, minWidth: 120 }}>
                      <InputLabel id="severity-select">Severity</InputLabel>
                      <Select
                        labelId="severity-select"
                        id="severity-select"
                        value={incident.severity}
                        disabled={waitingForSomething || incident.status === 'resolved'}
                        onChange={() => console.log('changed')}>
                        {severities.map((sev) => [
                          <MenuItem value={sev} key={sev}>
                            {sev}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>
                  </ListItem>
                  <Divider variant="middle" component="li" />
                  <CardHeader
                    avatar={<PeopleIcon sx={{ marginRight: 1 }} />}
                    title={`Roles`}
                    style={{
                      backgroundImage: acGradientPerTheme
                    }}
                  />
                  {waitingForSomething && (
                    <Box sx={{ width: '100%' }}>
                      <LinearProgress />
                    </Box>
                  )}

                  <ListItem dense key="roles">
                    <ListItemIcon>
                      <MilitaryTechIcon fontSize="large" />
                    </ListItemIcon>
                    <FormControl variant="standard" sx={{ m: 1, minWidth: 120 }}>
                      <InputLabel id="commander-select">Commander</InputLabel>
                      <Select
                        labelId="commander-select"
                        id="commander-select"
                        value={incident.commander !== null ? incident.commander : ''}
                        disabled={waitingForSomething || incident.status === 'resolved'}
                        onChange={handleUserAssign({
                          incidentID: incident.incident_id,
                          channelID: incident.channel_id,
                          messageTS: incident.bp_message_ts,
                          role: 'incident_commander'
                        })}>
                        {users.map((user) => [
                          <MenuItem value={user.name} key={user.name}>
                            {user.name}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>

                    <Divider orientation="vertical" flexItem />
                    <ListItemIcon>
                      <DeveloperBoardIcon fontSize="large" />
                    </ListItemIcon>
                    <FormControl variant="standard" sx={{ m: 1, minWidth: 120 }}>
                      <InputLabel id="tech-lead-select">Tech Lead</InputLabel>
                      <Select
                        labelId="tech-lead-select"
                        id="tech-lead-select"
                        value={incident.technical_lead !== null ? incident.technical_lead : ''}
                        disabled={waitingForSomething || incident.status === 'resolved'}
                        onChange={handleUserAssign({
                          incidentID: incident.incident_id,
                          channelID: incident.channel_id,
                          messageTS: incident.bp_message_ts,
                          role: 'technical_lead'
                        })}>
                        {users.map((user) => [
                          <MenuItem value={user.name} key={user.name}>
                            {user.name}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>

                    <Divider orientation="vertical" flexItem />
                    <ListItemIcon>
                      <ForumIcon fontSize="large" />
                    </ListItemIcon>
                    <FormControl variant="standard" sx={{ m: 1, minWidth: 120 }}>
                      <InputLabel id="communications-liaison-select">Comms</InputLabel>
                      <Select
                        labelId="communications-liaison-select"
                        id="communications-liaison-select"
                        value={
                          incident.communications_liaison !== null
                            ? incident.communications_liaison
                            : ''
                        }
                        disabled={waitingForSomething || incident.status === 'resolved'}
                        onChange={handleUserAssign({
                          incidentID: incident.incident_id,
                          channelID: incident.channel_id,
                          messageTS: incident.bp_message_ts,
                          role: 'communications_liaison'
                        })}>
                        {users.map((user) => [
                          <MenuItem value={user.name} key={user.name}>
                            {user.name}
                          </MenuItem>
                        ])}
                      </Select>
                    </FormControl>
                  </ListItem>

                  <Divider variant="middle" component="li" />
                  <CardHeader
                    avatar={<LabelIcon sx={{ marginRight: 1 }} />}
                    title={`Tags`}
                    style={{
                      backgroundImage: acGradientPerTheme
                    }}
                  />
                  <ListItem
                    key="tags"
                    sx={{
                      width: '100%'
                    }}>
                    <Stack direction="row" spacing={1}>
                      {incident.tags ? (
                        (incident.tags.includes(',')
                          ? incident.tags.split(',')
                          : [incident.tags]
                        ).map((tag, i) => [
                          i >= 0 && (
                            <Chip
                              color="default"
                              label={tag}
                              size="small"
                              //component="a"
                              //href={tag}
                              icon={<LabelIcon />}
                              //clickable
                              sx={{
                                ':hover': {
                                  bgcolor: 'primary.main',
                                  color: 'white'
                                }
                              }}></Chip>
                          )
                        ])
                      ) : (
                        <ListItemText
                          secondary={`No tags. You may optionally set tags on this incident.`}
                        />
                      )}
                    </Stack>
                  </ListItem>
                </List>
              </Card>

              <Card sx={{ marginTop: 4 }}>
                <AuditLogTable auditLogData={auditLogData} />
              </Card>
            </>
          ) : (
            <Container>
              <ListItem key={`empty-incident-list`}>
                <ListItemIcon>
                  <DoNotDisturbOnIcon />
                </ListItemIcon>
                <ListItemText
                  primary={`Incident not found.`}
                  secondary={`That incident wasn't found. Check the spelling and try again.`}
                />
              </ListItem>
            </Container>
          )}
        </Container>
      ) : (
        <Container sx={{ paddingTop: 5 }}>
          <Box sx={{ display: 'flex' }}>
            <CircularProgress />
          </Box>
        </Container>
      )}
      {fetchStatus && (
        <Container>
          <Snackbar
            open={openFetchStatus}
            autoHideDuration={6000}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            onClose={(event, reason) => {
              if (reason === 'clickaway') {
                return;
              }
              setOpenFetchStatus(false);
            }}>
            <Alert
              severity={fetchStatus ? fetchStatus : 'info'}
              variant="filled"
              sx={{ width: '100%' }}>
              {fetchMessage}
            </Alert>
          </Snackbar>
        </Container>
      )}
    </div>
  );
};

export default ViewSingleIncident;
