import { Alert, AlertTitle, Box, Grid, Typography } from '@mui/material';

const NotFoundPage = () => {
  return (
    <div
      className=""
      style={{
        height: '100vh'
      }}>
      <Grid
        container
        spacing={0}
        direction="column"
        alignItems="center"
        justifyContent="center"
        style={{ minHeight: '20vh' }}>
        <Grid item>
          <Box display="flex" justifyContent="center" sx={{ paddingBottom: 1, paddingTop: 8 }}>
            <Typography
              variant="h3"
              sx={{
                display: { xs: 'none', md: 'flex' },
                fontFamily: 'Roboto',
                fontWeight: 1000,
                letterSpacing: '.6rem'
              }}>
              OOPS
            </Typography>
          </Box>
          <Grid item>
            <Box
              display="flex"
              justifyContent="center"
              alignItems="center"
              sx={{ paddingBottom: 4, paddingTop: 1 }}>
              {' '}
              <Alert severity="error">
                <AlertTitle>Page Not Found</AlertTitle>
                That page was not found. If this is an error, report it.
              </Alert>
            </Box>
          </Grid>
        </Grid>
      </Grid>
    </div>
  );
};

export default NotFoundPage;
