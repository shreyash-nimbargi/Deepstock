try:
    from googlesearch import search
    print("Import successful")
    
    query = "Reliance stock news"
    print(f"Searching for: {query}")
    
    # Try with minimal arguments first
    results = list(search(query, stop=5))
    print(f"Found {len(results)} results (standard args)")
    for r in results:
        print(r)
        
except TypeError as e:
    print(f"TypeError with standard args: {e}")
    try:
        # Try with googlesearch-python args
        results = list(search(query, num_results=5))
        print(f"Found {len(results)} results (googlesearch-python args)")
        for r in results:
            print(r)
    except Exception as e2:
        print(f"Error with alternative args: {e2}")
except Exception as e:
    print(f"General Error: {e}")
