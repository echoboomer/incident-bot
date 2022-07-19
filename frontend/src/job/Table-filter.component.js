import { useState } from 'react';

import { FormControlLabel, IconButton, Menu, MenuItem, Switch, Tooltip } from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';

export default function TableFilterOptions(props) {
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <div>
      <Tooltip title={props.hoverMessage}>
        <IconButton
          id="um-button"
          aria-controls={open ? 'um-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
          onClick={handleClick}>
          <FilterListIcon />
        </IconButton>
      </Tooltip>
      <Menu
        id="um-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'um-button'
        }}>
        <MenuItem key="manage">
          <FormControlLabel
            control={
              <Switch
                checked={props.dense}
                size="small"
                onChange={props.handleChangeDense}
                sx={{ marginLeft: 2 }}
              />
            }
            label="Compact"
          />
        </MenuItem>
      </Menu>
    </div>
  );
}
