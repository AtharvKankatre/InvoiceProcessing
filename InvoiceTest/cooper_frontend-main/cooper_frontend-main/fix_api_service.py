
import os

file_path = r"d:\Inpinite\InvoiceTest\cooper_frontend-main\cooper_frontend-main\src\services\apiService.ts"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the start of the method to target
start_marker = "async exportPartHistory("
# The method ends before the class closing brace `}` which is usually the last `}` in the file, or close to it.
# Actually, let's just replace the whole known bad block if we can find it.
# The bad block contains `const headers = this.getAuthHeaders();`
# The good block should use `localStorage.getItem`.

if "const headers = this.getAuthHeaders();" in content:
    print("Found broken method. Fixing...")
    
    # We will replace the entire method body.
    # It starts at `async exportPartHistory(` and ends at the matching closing brace.
    # But regex replacement is risky without precise matching.
    # Let's use string replacement for the specific lines we know are wrong.
    
    bad_line_1 = "const fullUrl = `${API_BASE_URL}/${endpoint}`; // Ensure leading slash handling"
    bad_line_2 = "const headers = this.getAuthHeaders();"
    
    if bad_line_1 in content and bad_line_2 in content:
        # Construct the new implementation
        new_implementation = """    // Use direct fetch to handle Blob response
    const fullUrl = `${this.baseUrl}${endpoint}`; 
    const token = localStorage.getItem('access_token');
    
    const headers: HeadersInit = {
        'Authorization': `Bearer ${token}`
    };"""
        
        # Replace the bad lines with the new implementation
        # We need to be careful about what we replace.
        # The bad block in the file (from Step 4227) looks like:
        #     // Use direct fetch to handle Blob response
        #     const fullUrl = `${API_BASE_URL}/${endpoint}`; // Ensure leading slash handling
        #     const headers = this.getAuthHeaders();
        # 
        #     // Remove Content-Type header for GET request if it exists? 
        #     // Usually getAuthHeaders adds Content-Type: application/json. 
        #     // For GET it shouldn't matter but let's keep headers as is.
        # 
        #     const response = await fetch(fullUrl, {
        
        # specific string to target
        target_block = """    // Use direct fetch to handle Blob response
    const fullUrl = `${API_BASE_URL}/${endpoint}`; // Ensure leading slash handling
    const headers = this.getAuthHeaders();

    // Remove Content-Type header for GET request if it exists? 
    // Usually getAuthHeaders adds Content-Type: application/json. 
    // For GET it shouldn't matter but let's keep headers as is.

    const response = await fetch(fullUrl, {"""

        replacement_block = """    // Use direct fetch to handle Blob response
    const fullUrl = `${this.baseUrl}${endpoint}`; 
    const token = localStorage.getItem('access_token');
    
    const headers: HeadersInit = {
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(fullUrl, {"""
        
        # check if target block exists (ignoring whitespace might be needed but let's try direct first)
        # Actually, python `replace` is strict.
        # Let's simply rewrite the file by splitting at `exportPartHistory` and rebuilding the end.
        
        parts = content.split("async exportPartHistory(")
        if len(parts) > 1:
            preamble = parts[0]
            # The rest of the file...
            # We can just append the CORRECT method and the class closer.
            
            new_method = """async exportPartHistory(
    partNumber: string,
    fromDate?: string,
    toDate?: string
  ): Promise<Blob> {
    let endpoint = API_ENDPOINTS.PART_HISTORY_EXPORT(partNumber);

    // Build query parameters
    const params = new URLSearchParams();
    if (fromDate) params.append('from_date', fromDate);
    if (toDate) params.append('to_date', toDate);

    const queryString = params.toString();
    if (queryString) {
      endpoint = `${endpoint}?${queryString}`;
    }

    const fullUrl = `${this.baseUrl}${endpoint}`;
    const token = localStorage.getItem('access_token');
    
    const headers: HeadersInit = {
        'Authorization': `Bearer ${token}`
    };

    const response = await fetch(fullUrl, {
      method: 'GET',
      headers: headers,
    });

    if (!response.ok) {
        if (response.status === 401) {
            this.logout();
            throw new Error('Session expired. Please login again.');
        }
      throw new Error(`Export failed: ${response.status} ${response.statusText}`);
    }

    return await response.blob();
  }

}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
"""
            # Write back
            new_content = preamble + new_method
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Successfully rewrote exportPartHistory method.")
        else:
            print("Could not split by exportPartHistory.")
    else:
        print("Could not find specific bad lines.")
else:
    print("Method seems to be already fixed or missing bad lines.")
