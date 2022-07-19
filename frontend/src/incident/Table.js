import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { alpha } from '@mui/material/styles';

import {
  Badge,
  Box,
  Checkbox,
  Chip,
  IconButton,
  Link,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Toolbar,
  Tooltip,
  Typography
} from '@mui/material';

import AddAlertIcon from '@mui/icons-material/AddAlert';
import DeleteIcon from '@mui/icons-material/Delete';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import CircleNotificationsIcon from '@mui/icons-material/CircleNotifications';
import EditIcon from '@mui/icons-material/Edit';
import { visuallyHidden } from '@mui/utils';

import { Icon } from '@iconify/react';
import { titleCase } from '../shared/titleCase';
import moment from 'moment';
import TableFilterOptions from './Table-filter.component';
import TableSearch from '../components/Search.component';
import { slackWorkspaceID } from '../shared/Variables';

function descendingComparator(a, b, orderBy) {
  if (b[orderBy] < a[orderBy]) {
    return -1;
  }
  if (b[orderBy] > a[orderBy]) {
    return 1;
  }
  return 0;
}

// Age of incident
function daysOld(creationDate) {
  var dateCreated = new Date(moment(creationDate, 'YYYY-MM-DD HH:mm:ss'));
  var today = new Date();
  var diff = (today.getTime() - dateCreated.getTime()) / (1000 * 3600 * 24);

  return `${dateCreated.toDateString()} (${diff.toFixed()} days)`;
}

function getComparator(order, orderBy) {
  return order === 'desc'
    ? (a, b) => descendingComparator(a, b, orderBy)
    : (a, b) => -descendingComparator(a, b, orderBy);
}

function stableSort(array, comparator) {
  const stabilizedThis = array.map((el, index) => [el, index]);
  stabilizedThis.sort((a, b) => {
    const order = comparator(a[0], b[0]);
    if (order !== 0) {
      return order;
    }
    return a[1] - b[1];
  });
  return stabilizedThis.map((el) => el[0]);
}

const headCells = [
  {
    id: 'incident_id',
    numeric: false,
    disablePadding: false,
    label: 'Incident ID'
  },
  {
    id: 'severity',
    numeric: false,
    disablePadding: false,
    label: 'Severity'
  },
  {
    id: 'status',
    numeric: false,
    disablePadding: false,
    label: 'Status'
  },
  {
    id: 'created_at',
    numeric: false,
    disablePadding: false,
    label: 'Created'
  },
  {
    id: 'updated_at',
    numeric: false,
    disablePadding: false,
    label: 'Updated'
  },
  {
    id: 'last_comms',
    numeric: false,
    disablePadding: false,
    label: 'Last Comms'
  },
  {
    id: 'slack_channel',
    numeric: false,
    disablePadding: false,
    label: 'Slack Channel'
  }
];

function EnhancedTableHead(props) {
  const { onSelectAllClick, order, orderBy, numSelected, rowCount, onRequestSort } = props;
  const createSortHandler = (property) => (event) => {
    onRequestSort(event, property);
  };

  return (
    <TableHead>
      <TableRow>
        <TableCell padding="checkbox">
          <Checkbox
            color="primary"
            indeterminate={numSelected > 0 && numSelected < rowCount}
            checked={rowCount > 0 && numSelected === rowCount}
            onChange={onSelectAllClick}
            inputProps={{
              'aria-label': 'select all incidents'
            }}
          />
        </TableCell>
        {headCells.map((headCell) => (
          <TableCell
            key={headCell.id}
            align={headCell.numeric ? 'right' : 'left'}
            padding={headCell.disablePadding ? 'none' : 'normal'}
            sortDirection={orderBy === headCell.id ? order : false}>
            <TableSortLabel
              active={orderBy === headCell.id}
              direction={orderBy === headCell.id ? order : 'asc'}
              onClick={createSortHandler(headCell.id)}>
              <b>{headCell.label}</b>
              {orderBy === headCell.id ? (
                <Box component="span" sx={visuallyHidden}>
                  {order === 'desc' ? 'sorted descending' : 'sorted ascending'}
                </Box>
              ) : null}
            </TableSortLabel>
          </TableCell>
        ))}
      </TableRow>
    </TableHead>
  );
}

EnhancedTableHead.propTypes = {
  numSelected: PropTypes.number.isRequired,
  onRequestSort: PropTypes.func.isRequired,
  onSelectAllClick: PropTypes.func.isRequired,
  order: PropTypes.oneOf(['asc', 'desc']).isRequired,
  orderBy: PropTypes.string.isRequired,
  rowCount: PropTypes.number.isRequired
};

const EnhancedTableToolbar = (props) => {
  const {
    dense,
    handleChangeDense,
    handleChangeHideResolved,
    hideResolved,
    numSelected,
    setQuery
  } = props;
  return (
    <Toolbar
      sx={{
        pl: { sm: 2 },
        pr: { xs: 1, sm: 1 },
        ...(numSelected > 0 && {
          bgcolor: (theme) =>
            alpha(theme.palette.primary.main, theme.palette.action.activatedOpacity)
        })
      }}>
      {numSelected > 0 ? (
        <Typography sx={{ flex: '1 1 100%' }} color="inherit" variant="subtitle1" component="div">
          {numSelected} selected
        </Typography>
      ) : (
        <Typography sx={{ flex: '1 1 100%' }} variant="h6" id="tableTitle" component="div">
          Incidents
        </Typography>
      )}

      {numSelected > 0 ? (
        <DeleteIcon />
      ) : (
        <>
          <Box
            sx={{
              display: 'inline-flex'
            }}>
            <TableSearch setQuery={setQuery.bind()} />
            <TableFilterOptions
              dense={dense}
              handleChangeDense={handleChangeDense}
              handleChangeHideResolved={handleChangeHideResolved}
              hideResolved={hideResolved}
              hoverMessage={`Table filter options`}
              setQuery={setQuery.bind()}
            />
          </Box>
        </>
      )}
    </Toolbar>
  );
};

EnhancedTableToolbar.propTypes = {
  dense: PropTypes.bool.isRequired,
  handleChangeDense: PropTypes.func.isRequired,
  handleChangeHideResolved: PropTypes.func.isRequired,
  hideResolved: PropTypes.bool.isRequired,
  numSelected: PropTypes.number.isRequired,
  setQuery: PropTypes.func.isRequired
};

export default function EnhancedTable(props) {
  const [order, setOrder] = useState('desc');
  const [orderBy, setOrderBy] = useState('created_at');
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(0);
  const [dense, setDense] = useState(true);
  const [hideResolved, setHideResolved] = useState(false);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [query, setQuery] = useState('');

  const handleRequestSort = (event, property) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const handleSelectAllClick = (event) => {
    if (event.target.checked) {
      const newSelecteds = filteredIncidentsData.map((n) => n.incident_id);
      setSelected(newSelecteds);
      return;
    }
    setSelected([]);
  };

  const handleClick = (event, name) => {
    const selectedIndex = selected.indexOf(name);
    let newSelected = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, name);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1)
      );
    }

    setSelected(newSelected);
  };

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleChangeDense = (event) => {
    setDense(event.target.checked);
  };

  const handleChangeHideResolved = (event) => {
    setHideResolved(event.target.checked);
  };

  const isSelected = (name) => selected.indexOf(name) !== -1;

  // Avoid a layout jump when reaching the last page with empty rows.
  const emptyRows =
    page > 0 ? Math.max(0, (1 + page) * rowsPerPage - filteredIncidentsData.length) : 0;

  // Render incidents based on requested options
  // i.e. hide resolved, etc.
  function filterData(hideResolved, query, incidents) {
    var r = incidents;
    if (hideResolved) {
      r = r.filter((incident) => incident.status !== 'resolved');
    }
    if (query !== null) {
      r = r.filter((incident) => incident.incident_id.includes(query));
    }
    return r;
  }

  const filteredIncidentsData = filterData(hideResolved, query, props.incidents);

  return (
    <Box sx={{ width: '100%' }}>
      <Paper sx={{ width: '100%', mb: 2 }}>
        <EnhancedTableToolbar
          dense={dense}
          handleChangeDense={handleChangeDense}
          handleChangeHideResolved={handleChangeHideResolved}
          hideResolved={hideResolved}
          numSelected={selected.length}
          setQuery={setQuery.bind()}
        />
        <TableContainer>
          <Table
            sx={{ minWidth: 750 }}
            aria-labelledby="tableTitle"
            size={dense ? 'small' : 'medium'}>
            <EnhancedTableHead
              numSelected={selected.length}
              order={order}
              orderBy={orderBy}
              onSelectAllClick={handleSelectAllClick}
              onRequestSort={handleRequestSort}
              rowCount={filteredIncidentsData.length}
            />
            <TableBody>
              {filteredIncidentsData.length > 0 ? (
                stableSort(filteredIncidentsData, getComparator(order, orderBy))
                  .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                  .map((row, index) => {
                    const isItemSelected = isSelected(row.incident_id);
                    const labelId = `enhanced-table-checkbox-${index}`;

                    return (
                      <TableRow
                        hover
                        onClick={(event) => handleClick(event, row.incident_id)}
                        role="checkbox"
                        aria-checked={isItemSelected}
                        tabIndex={-1}
                        key={row.incident_id}
                        selected={isItemSelected}>
                        <TableCell padding="checkbox">
                          <Checkbox
                            color="primary"
                            checked={isItemSelected}
                            inputProps={{
                              'aria-labelledby': labelId
                            }}
                          />
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          <Tooltip title="Edit this Incident">
                            <Link
                              href={`/app/incidents/${row.incident_id}`}
                              underline="hover"
                              sx={{
                                color: 'default',
                                '&:hover': {
                                  color: 'info.light'
                                }
                              }}>
                              <EditIcon fontSize="small" />
                              {row.incident_id}
                            </Link>
                          </Tooltip>
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          <Chip
                            label={row.severity.toUpperCase()}
                            size="small"
                            color={
                              row.severity === 'sev1'
                                ? 'error'
                                : row.severity === 'sev2'
                                ? 'warning'
                                : row.severity === 'sev3'
                                ? 'warning'
                                : 'success'
                            }
                          />
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          <Chip
                            label={titleCase(row.status)}
                            size="small"
                            color={row.status === 'resolved' ? 'success' : 'warning'}
                          />
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          {row.created_at !== null && (
                            <>
                              <Box>
                                <CalendarTodayIcon fontSize="small" sx={{ pr: 0.5 }} />
                                {daysOld(row.created_at)}
                              </Box>
                            </>
                          )}
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          {row.updated_at !== null && (
                            <>
                              <Box>
                                <Badge
                                  color={row.status === 'resolved' ? 'success' : 'error'}
                                  variant="dot"
                                  sx={{ mr: 1 }}
                                />
                                {new Date(
                                  moment(row.updated_at, 'YYYY-MM-DD HH:mm:ss')
                                ).toDateString()}
                              </Box>
                            </>
                          )}
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          {row.severity === 'sev2' || row.severity === 'sev1' ? (
                            row.last_update_sent !== null ? (
                              <>
                                <Box>
                                  <Badge
                                    color={row.status === 'resolved' ? 'success' : 'error'}
                                    variant="dot"
                                    sx={{ mr: 1 }}
                                  />
                                  {new Date(
                                    moment(row.last_update_sent, 'YYYY-MM-DD HH:mm:ss')
                                  ).toDateString()}
                                </Box>
                              </>
                            ) : (
                              <>
                                <Tooltip
                                  title={`Required for ${row.severity.toUpperCase()} incidents.`}>
                                  <AddAlertIcon fontSize="small" color="error" />
                                </Tooltip>
                              </>
                            )
                          ) : (
                            <>
                              <Tooltip
                                title={`Optional for ${row.severity.toUpperCase()} incidents.`}>
                                <CircleNotificationsIcon fontSize="small" color="info" />
                              </Tooltip>
                            </>
                          )}
                        </TableCell>
                        <TableCell align="left" padding="normal">
                          <IconButton
                            key={`${row.incident_id}-slack-link`}
                            component="a"
                            href={`https://${slackWorkspaceID}.slack.com/archives/${row.channel_id}`}
                            target="new">
                            <Icon icon="bxl:slack" width="20" height="20" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  })
              ) : (
                <>
                  <TableRow
                    style={{
                      height: (dense ? 33 : 53) * emptyRows
                    }}>
                    <TableCell colSpan={8}>No results.</TableCell>
                  </TableRow>
                </>
              )}
              {emptyRows > 0 && (
                <TableRow
                  style={{
                    height: (dense ? 33 : 53) * emptyRows
                  }}>
                  <TableCell colSpan={6} />
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[5, 15, 25, 50, 100]}
          component="div"
          count={filteredIncidentsData.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>
    </Box>
  );
}
