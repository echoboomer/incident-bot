import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { apiUrl } from '../shared/Variables';
import OnCallTable from './Table';

import { Alert, Box, CircularProgress, Container, Snackbar } from '@mui/material';

const OnCall = () => {
  const [onCallData, setOnCallData] = useState();
  const [refreshData, setRefreshData] = useState(false);

  const [fetchOnCallDataStatus, setFetchOnCallDataStatus] = useState('');
  const [fetchOnCallDataMessage, setFetchOnCallDataMessage] = useState('');
  const [openFetchOnCallDataStatus, setOpenFetchOnCallDataStatus] = useState(false);

  function getOnCallData() {
    axios({
      method: 'GET',
      responseType: 'json',
      url: apiUrl + '/pager'
    })
      .then(function (response) {
        setFetchOnCallDataStatus('success');
        setFetchOnCallDataMessage(`Successfully retrieved on-call data from backend!`);
        setOpenFetchOnCallDataStatus(true);
        setOnCallData(response.data);
      })
      .catch(function (error) {
        if (error.response) {
          setFetchOnCallDataStatus('error');
          setFetchOnCallDataMessage(
            `Error retrieving on-call data from backend: ${error.response.data.error}`
          );
          setOpenFetchOnCallDataStatus(true);
        } else if (error.request) {
          setFetchOnCallDataStatus('error');
          setFetchOnCallDataMessage(`Error retrieving on-call data from backend: ${error}`);
          setOpenFetchOnCallDataStatus(true);
        }
      });
  }

  // Retrieve on-call data
  useEffect(() => {
    getOnCallData();
  }, []);

  if (refreshData) {
    setRefreshData(false);
    getOnCallData();
  }

  return (
    <div className="align-items-center justify-content-center" style={{ paddingTop: '5vh' }}>
      <Container maxWidth="" sx={{ width: '70%' }}>
        {onCallData !== undefined ? (
          <OnCallTable data={onCallData} />
        ) : (
          <Box sx={{ display: 'flex' }}>
            <CircularProgress />
          </Box>
        )}
      </Container>
      {fetchOnCallDataStatus && (
        <Container>
          <Snackbar
            open={openFetchOnCallDataStatus}
            autoHideDuration={6000}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            onClose={(event, reason) => {
              if (reason === 'clickaway') {
                return;
              }
              setOpenFetchOnCallDataStatus(false);
            }}>
            <Alert
              severity={fetchOnCallDataStatus ? fetchOnCallDataStatus : 'info'}
              variant="filled"
              sx={{ width: '100%' }}>
              {fetchOnCallDataMessage}
            </Alert>
          </Snackbar>
        </Container>
      )}
    </div>
  );
};

export default OnCall;
