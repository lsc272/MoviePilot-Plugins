function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

function clone(value) {
  return JSON.parse(JSON.stringify(value || {}))
}

export { clone as c, unwrapResponse as u };
